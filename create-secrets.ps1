# PowerShell script to create AWS Secrets Manager secrets for TL;DW API keys
# Replace [OPENAI_API_KEY] and [RESEND_API_KEY] with actual values before running

# Create OpenAI API key secret
Write-Host "Creating OpenAI API key secret..."
$openaiResult = aws secretsmanager create-secret `
    --name "tldw-openai-api-key" `
    --description "OpenAI API key for TL;DW application" `
    --secret-string "[OPENAI_API_KEY]" `
    --region us-west-2

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ OpenAI secret created successfully"
    $openaiArn = ($openaiResult | ConvertFrom-Json).ARN
    Write-Host "OpenAI Secret ARN: $openaiArn"
} else {
    Write-Host "❌ Failed to create OpenAI secret"
}

# Create Resend API key secret
Write-Host "`nCreating Resend API key secret..."
$resendResult = aws secretsmanager create-secret `
    --name "tldw-resend-api-key" `
    --description "Resend API key for TL;DW application email service" `
    --secret-string "[RESEND_API_KEY]" `
    --region us-west-2

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Resend secret created successfully"
    $resendArn = ($resendResult | ConvertFrom-Json).ARN
    Write-Host "Resend Secret ARN: $resendArn"
} else {
    Write-Host "❌ Failed to create Resend secret"
}

# Output ARNs for apprunner.yaml configuration
Write-Host "`n📋 Copy these ARNs for your apprunner.yaml configuration:"
Write-Host "OPENAI_API_KEY ARN: $openaiArn"
Write-Host "RESEND_API_KEY ARN: $resendArn"

# Save ARNs to a file for reference
@"
# AWS Secrets Manager ARNs for TL;DW Application
# Generated on $(Get-Date)

OPENAI_API_KEY_ARN=$openaiArn
RESEND_API_KEY_ARN=$resendArn
"@ | Out-File -FilePath "secret-arns.txt" -Encoding UTF8

Write-Host "`n💾 ARNs saved to secret-arns.txt for reference"