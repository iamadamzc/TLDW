# TL;DW Deployment Makefile

.PHONY: help build test deploy clean

# Default target
help:
	@echo "TL;DW Deployment Commands:"
	@echo ""
	@echo "  make build    - Build Docker image locally"
	@echo "  make test     - Test dependencies in container"
	@echo "  make deploy   - Build and push to ECR for App Runner"
	@echo "  make clean    - Clean up local Docker images"
	@echo ""

# Build Docker image locally
build:
	@echo "🔨 Building Docker image..."
	docker build -t tldw:latest .
	@echo "✅ Build complete"

# Test dependencies in the built container
test: build
	@echo "🧪 Testing dependencies in container..."
	docker run --rm tldw:latest python3 test_dependencies.py
	@echo "✅ Container tests complete"

# Deploy to ECR for App Runner
deploy:
	@echo "🚀 Deploying to ECR..."
	./deploy.sh
	@echo "✅ Deployment complete"

# Clean up local Docker images
clean:
	@echo "🧹 Cleaning up Docker images..."
	-docker rmi tldw:latest
	-docker rmi 528131355234.dkr.ecr.us-west-2.amazonaws.com/tldw:latest
	@echo "✅ Cleanup complete"

# Quick local test without building
test-local:
	@echo "🧪 Testing dependencies locally..."
	python3 test_dependencies.py