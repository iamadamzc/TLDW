# PowerShell deployment script for App Runner
# Equivalent to deploy-apprunner.sh but for Windows PowerShell

$ErrorActionPreference = "Stop"

# Configuration
$AWS_REGION = "us-west-2"
$AWS_ACCOUNT_ID = "528131355234"
$ECR_REPOSITORY = "tldw"
$SERVICE_NAME = "tldw-container-app-v4"

# Create unique tag
$DATE_TAG = Get-Date -Format "yyyyMMdd-HHmmss"
$IMAGE_TAG = "ytdlp-fix-$DATE_TAG"
$REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
$ECR_URI = "${REGISTRY}/${ECR_REPOSITORY}"
$IMAGE_URI = "${ECR_URI}:${IMAGE_TAG}"

Write-Host "=== App Runner Deployment (PowerShell) ===" -ForegroundColor Cyan
Write-Host "AWS Region: $AWS_REGION"
Write-Host "ECR Repository: $ECR_URI"
Write-Host "Container Tag: $IMAGE_TAG"
Write-Host "Image URI: $IMAGE_URI"
Write-Host ""

# Preflight checks
Write-Host "🔍 Running preflight checks..." -ForegroundColor Yellow

# Check AWS CLI
try {
    aws sts get-caller-identity | Out-Null
    Write-Host "✅ AWS CLI configured" -ForegroundColor Green
}
catch {
    Write-Host "❌ AWS CLI not configured" -ForegroundColor Red
    exit 1
}

# Check Docker
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker is not running" -ForegroundColor Red
    exit 1
}

# Get App Runner service ARN
Write-Host "🔍 Finding App Runner service..." -ForegroundColor Yellow
$SERVICE_ARN = aws apprunner list-services --region $AWS_REGION --query "ServiceSummaryList[?ServiceName=='$SERVICE_NAME'].ServiceArn" --output text

if (-not $SERVICE_ARN -or $SERVICE_ARN -eq "None") {
    Write-Host "❌ Could not find App Runner service: $SERVICE_NAME" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Found service: $SERVICE_NAME" -ForegroundColor Green
Write-Host "   ARN: $SERVICE_ARN"

# ECR Login
Write-Host ""
Write-Host "🔐 Logging into ECR..." -ForegroundColor Yellow
$LOGIN_PASSWORD = aws ecr get-login-password --region $AWS_REGION
$LOGIN_PASSWORD | docker login --username AWS --password-stdin $REGISTRY
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ECR login failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ ECR login successful" -ForegroundColor Green

# Build Docker image
Write-Host ""
Write-Host "🔨 Building Docker image: $IMAGE_URI..." -ForegroundColor Yellow
docker build --no-cache --pull --build-arg CACHE_BUSTER="$IMAGE_TAG" -t "${ECR_REPOSITORY}:$IMAGE_TAG" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Build complete" -ForegroundColor Green

# Tag for ECR
Write-Host ""
Write-Host "🏷️  Tagging image for ECR..." -ForegroundColor Yellow
docker tag "${ECR_REPOSITORY}:$IMAGE_TAG" $IMAGE_URI
docker tag "${ECR_REPOSITORY}:$IMAGE_TAG" "${ECR_URI}:latest"
Write-Host "✅ Tagged: $IMAGE_URI" -ForegroundColor Green
Write-Host "✅ Tagged: ${ECR_URI}:latest" -ForegroundColor Green

# Push to ECR
Write-Host ""
Write-Host "⬆️  Pushing image to ECR..." -ForegroundColor Yellow
docker push $IMAGE_URI
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker push failed" -ForegroundColor Red
    exit 1
}
docker push "${ECR_URI}:latest"
Write-Host "✅ Pushed: $IMAGE_URI" -ForegroundColor Green
Write-Host "✅ Pushed: ${ECR_URI}:latest" -ForegroundColor Green

# Get current config
Write-Host ""
Write-Host "🔄 Preparing App Runner update..." -ForegroundColor Yellow
$CURRENT_CONFIG = aws apprunner describe-service --service-arn $SERVICE_ARN --region $AWS_REGION | ConvertFrom-Json
$PREVIOUS_IMAGE = $CURRENT_CONFIG.Service.SourceConfiguration.ImageRepository.ImageIdentifier
Write-Host "📝 Previous image: $PREVIOUS_IMAGE"

# Update App Runner
Write-Host ""
Write-Host "🚀 Starting App Runner deployment..." -ForegroundColor Yellow
$UPDATE_CONFIG = @{
    ImageRepository        = @{
        ImageIdentifier     = $IMAGE_URI
        ImageRepositoryType = "ECR"
    }
    AutoDeploymentsEnabled = $false
} | ConvertTo-Json -Depth 10 -Compress

aws apprunner update-service --service-arn $SERVICE_ARN --region $AWS_REGION --source-configuration $UPDATE_CONFIG
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ App Runner update failed" -ForegroundColor Red
    Write-Host ""
    Write-Host "🔄 ROLLBACK COMMAND:" -ForegroundColor Yellow
    Write-Host "aws apprunner update-service --service-arn `"$SERVICE_ARN`" --region `"$AWS_REGION`" --source-configuration '{`"ImageRepository`":{`"ImageIdentifier`":`"$PREVIOUS_IMAGE`",`"ImageRepositoryType`":`"ECR`"}}'" -ForegroundColor Cyan
    exit 1
}
Write-Host "✅ App Runner service update initiated" -ForegroundColor Green

# Wait for deployment
Write-Host ""
Write-Host "⏳ Waiting for deployment to complete..." -ForegroundColor Yellow
$elapsed = 0
$timeout = 600
$pollInterval = 15

while ($elapsed -lt $timeout) {
    $serviceInfo = aws apprunner describe-service --service-arn $SERVICE_ARN --region $AWS_REGION | ConvertFrom-Json
    $status = $serviceInfo.Service.Status
    $currentImage = $serviceInfo.Service.SourceConfiguration.ImageRepository.ImageIdentifier
    
    Write-Host "   Status: $status - $elapsed seconds" -ForegroundColor Cyan
    
    if ($status -eq "RUNNING" -and $currentImage -eq $IMAGE_URI) {
        Write-Host "✅ Service is RUNNING with new image!" -ForegroundColor Green
        break
    }
    
    if ($status -match "FAILED") {
        Write-Host "❌ Deployment failed with status: $status" -ForegroundColor Red
        exit 1
    }
    
    Start-Sleep -Seconds $pollInterval
    $elapsed += $pollInterval
}

if ($elapsed -ge $timeout) {
    Write-Host "⚠️  Deployment timeout after $timeout seconds" -ForegroundColor Yellow
    exit 1
}

# Get service URL
Write-Host ""
Write-Host "🎉 Deployment completed!" -ForegroundColor Green
$FINAL_INFO = aws apprunner describe-service --service-arn $SERVICE_ARN --region $AWS_REGION | ConvertFrom-Json
$SERVICE_URL = $FINAL_INFO.Service.ServiceUrl

Write-Host ""
Write-Host "📊 Summary:" -ForegroundColor Cyan
Write-Host "   Image URI: $IMAGE_URI" -ForegroundColor White
Write-Host "   Service ARN: $SERVICE_ARN" -ForegroundColor White
if ($SERVICE_URL) {
    Write-Host "   Service URL: https://$SERVICE_URL" -ForegroundColor White
    Write-Host "   Health: https://$SERVICE_URL/healthz" -ForegroundColor White
}
Write-Host ""
Write-Host "✅ New code is now running with tag: $IMAGE_TAG" -ForegroundColor Green
