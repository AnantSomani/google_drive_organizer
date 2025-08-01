.PHONY: setup dev test lint build clean infra-provision

setup: ## One-shot dev environment setup
	@echo "🚀 Setting up Drive Organizer development environment..."
	pnpm install
	cd apps/api && poetry install
	@echo "✅ Development setup complete!"

dev: ## Start development servers
	@echo "🔄 Starting development servers..."
	pnpm dev

test: ## Run all tests
	@echo "🧪 Running tests..."
	pnpm test

lint: ## Run linting
	@echo "🔍 Running linting..."
	pnpm lint

build: ## Build for production
	@echo "🏗️ Building for production..."
	pnpm build

clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	rm -rf apps/web/.next
	rm -rf apps/web/out
	rm -rf apps/api/__pycache__
	rm -rf apps/api/*/__pycache__
	find . -name "*.pyc" -delete

infra-provision: ## Provision infrastructure
	@echo "🏗️ Provisioning infrastructure..."
	./scripts/provision.sh

help: ## Show this help message
	@echo "Drive Organizer - Available Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' 