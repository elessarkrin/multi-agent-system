#!/bin/bash

# MultiAgent System Docker Setup Script
# This script handles model downloading and server startup

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MODEL_DIR="./models"
COMPOSE_FILE="docker-compose.yml"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Checking requirements..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "docker-compose.yml not found in current directory"
        exit 1
    fi

    log_success "Requirements check passed"
}

create_model_dir() {
    if [ ! -d "$MODEL_DIR" ]; then
        log_info "Creating models directory..."
        mkdir -p "$MODEL_DIR"
        log_success "Models directory created"
    else
        log_info "Models directory already exists"
    fi
}

download_model() {
    log_info "Downloading model (this may take a while)..."

    if docker compose run --rm model-downloader; then
        log_success "Model downloaded successfully"
    else
        log_error "Model download failed"
        exit 1
    fi
}

check_model_exists() {
    log_info "Checking if model file exists..."

    # Check for common model file patterns
    model_files=(
        "$MODEL_DIR"/*.gguf
        "$MODEL_DIR"/*/*.gguf
        "$MODEL_DIR"/*/*/*.gguf
    )

    for pattern in "${model_files[@]}"; do
        if ls $pattern 1> /dev/null 2>&1; then
            log_success "Model file(s) found"
            ls -la $pattern
            return 0
        fi
    done

    log_warning "No .gguf model files found in $MODEL_DIR"
    return 1
}

start_server() {
    log_info "Starting LLaMA server..."

    if docker compose up llama-server; then
        log_success "Server started successfully"
    else
        log_error "Failed to start server"
        exit 1
    fi
}

stop_services() {
    log_info "Stopping all services..."
    docker compose down
    log_success "Services stopped"
}

cleanup() {
    log_info "Cleaning up containers and images..."
    docker compose down --rmi local --volumes --remove-orphans
    log_success "Cleanup completed"
}

show_help() {
    echo "MultiAgent System Docker Setup Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup     - Download model and start server (default)"
    echo "  download  - Download model only"
    echo "  start     - Start server only"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart server"
    echo "  status    - Show service status"
    echo "  logs      - Show server logs"
    echo "  cleanup   - Remove containers, images, and volumes"
    echo "  check     - Check if model exists"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup     # Full setup (download + start)"
    echo "  $0 download  # Download model only"
    echo "  $0 start     # Start server only"
    echo "  $0 logs      # View server logs"
}

# Main script logic
case "${1:-setup}" in
    "setup")
        log_info "Starting full setup..."
        check_requirements
        create_model_dir

        if ! check_model_exists; then
            download_model
        else
            log_info "Model already exists, skipping download"
        fi

        start_server
        ;;

    "download")
        log_info "Downloading model only..."
        check_requirements
        create_model_dir
        download_model
        ;;

    "start")
        log_info "Starting server only..."
        check_requirements

        if ! check_model_exists; then
            log_error "No model found. Run '$0 download' first."
            exit 1
        fi

        start_server
        ;;

    "stop")
        stop_services
        ;;

    "restart")
        log_info "Restarting server..."
        docker compose restart llama-server
        log_success "Server restarted"
        ;;

    "status")
        log_info "Service status:"
        docker compose ps
        ;;

    "logs")
        log_info "Showing server logs (Ctrl+C to exit):"
        docker compose logs -f llama-server
        ;;

    "check")
        check_model_exists
        ;;

    "cleanup")
        cleanup
        ;;

    "help"|"-h"|"--help")
        show_help
        ;;

    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
