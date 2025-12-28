#!/bin/bash

# Subscription Tracker - Quick Deploy Script
# This script automates the deployment process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="subscription-tracker"
HELM_RELEASE="subscription-tracker"
HELM_CHART="./helm-charts/subscription-tracker"

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}OK $1${NC}"
}

print_error() {
    echo -e "${RED}X $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}WARNING $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    print_success "kubectl found"
    
    # Check helm
    if ! command -v helm &> /dev/null; then
        print_error "helm not found. Please install Helm 3."
        exit 1
    fi
    print_success "helm found"
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
        exit 1
    fi
    print_success "Connected to Kubernetes cluster"
    
    echo ""
}

build_image() {
    print_header "Building Docker Image"
    
    read -p "Enter Docker registry (e.g., ghcr.io/username): " REGISTRY
    read -p "Enter image tag (default: latest): " TAG
    TAG=${TAG:-latest}
    
    IMAGE_NAME="$REGISTRY/subscription-tracker:$TAG"
    
    echo "Building image: $IMAGE_NAME"
    cd app
    docker build -t "$IMAGE_NAME" .
    
    print_success "Image built successfully"
    
    read -p "Push image to registry? (y/n): " PUSH
    if [[ $PUSH == "y" || $PUSH == "Y" ]]; then
        docker push "$IMAGE_NAME"
        print_success "Image pushed to registry"
    fi
    
    cd ..
    echo ""
}

deploy_with_helm() {
    print_header "Deploying with Helm"
    
    # Create values override file
    cat > /tmp/custom-values.yaml <<EOF
flask:
  image:
    repository: ${REGISTRY}/subscription-tracker
    tag: ${TAG}
  replicaCount: 2

mysql:
  secrets:
    rootPassword: "$(openssl rand -base64 32)"
    userPassword: "$(openssl rand -base64 32)"
  persistence:
    size: 10Gi

loadBalancer:
  enabled: true
EOF
    
    # Install or upgrade
    if helm list -n "$NAMESPACE" | grep -q "$HELM_RELEASE"; then
        print_warning "Release exists. Upgrading..."
        helm upgrade "$HELM_RELEASE" "$HELM_CHART" \
            --namespace "$NAMESPACE" \
            -f /tmp/custom-values.yaml \
            --wait
    else
        helm install "$HELM_RELEASE" "$HELM_CHART" \
            --namespace "$NAMESPACE" \
            --create-namespace \
            -f /tmp/custom-values.yaml \
            --wait
    fi
    
    print_success "Deployment completed"
    echo ""
}

verify_deployment() {
    print_header "Verifying Deployment"
    
    echo "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod -l app=flask-app -n "$NAMESPACE" --timeout=300s
    kubectl wait --for=condition=ready pod -l app=mysql -n "$NAMESPACE" --timeout=300s
    
    print_success "All pods are ready"
    
    echo ""
    echo "Pod Status:"
    kubectl get pods -n "$NAMESPACE"
    
    echo ""
    echo "Service Status:"
    kubectl get svc -n "$NAMESPACE"
    
    echo ""
}

get_access_info() {
    print_header "Access Information"
    
    # Get LoadBalancer IP
    LB_IP=$(kubectl get svc flask-loadbalancer -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
    
    if [ -n "$LB_IP" ]; then
        echo "LoadBalancer URL: http://$LB_IP"
    else
        print_warning "LoadBalancer IP not yet assigned. Checking NodePort..."
        NODE_PORT=$(kubectl get svc flask-nodeport -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
        if [ -n "$NODE_PORT" ]; then
            echo "NodePort: $NODE_PORT"
            echo "Access via: http://<NODE-IP>:$NODE_PORT"
        fi
    fi
    
    echo ""
    echo "Port Forward command:"
    echo "kubectl port-forward svc/flask-service -n $NAMESPACE 8080:5000"
    echo "Then access: http://localhost:8080"
    
    echo ""
}

create_admin_user() {
    print_header "Create Admin User"
    
    read -p "Create admin user? (y/n): " CREATE_ADMIN
    if [[ $CREATE_ADMIN != "y" && $CREATE_ADMIN != "Y" ]]; then
        return
    fi
    
    read -p "Enter username to make admin: " USERNAME
    
    POD=$(kubectl get pod -l app=flask-app -n "$NAMESPACE" -o jsonpath='{.items[0].metadata.name}')
    
    kubectl exec -it "$POD" -n "$NAMESPACE" -- python -c "
import mysql.connector
conn = mysql.connector.connect(
    host='mysql-service',
    user='root',
    password='rootpassword',
    database='subscription_tracker'
)
cursor = conn.cursor()
cursor.execute('UPDATE users SET is_admin = TRUE WHERE username = \"$USERNAME\"')
conn.commit()
print('User $USERNAME is now admin!')
"
    
    print_success "Admin user created"
    echo ""
}

run_trivy_scan() {
    print_header "Running Trivy Security Scan"
    
    if ! command -v trivy &> /dev/null; then
        print_warning "Trivy not installed. Skipping scan."
        return
    fi
    
    echo "Scanning image: $IMAGE_NAME"
    trivy image "$IMAGE_NAME" --severity HIGH,CRITICAL
    
    echo ""
}

show_logs() {
    print_header "Recent Logs"
    
    echo "Flask Application Logs:"
    kubectl logs -l app=flask-app -n "$NAMESPACE" --tail=20
    
    echo ""
    echo "MySQL Logs:"
    kubectl logs -l app=mysql -n "$NAMESPACE" --tail=20
    
    echo ""
}

cleanup() {
    print_header "Cleanup"
    
    read -p "Are you sure you want to delete the deployment? (yes/no): " CONFIRM
    if [[ $CONFIRM != "yes" ]]; then
        print_warning "Cleanup cancelled"
        return
    fi
    
    helm uninstall "$HELM_RELEASE" -n "$NAMESPACE"
    kubectl delete namespace "$NAMESPACE"
    
    print_success "Cleanup completed"
}

main_menu() {
    while true; do
        echo ""
        print_header "Subscription Tracker - Deployment Menu"
        echo "1. Full Deployment (Build + Deploy)"
        echo "2. Build Docker Image Only"
        echo "3. Deploy with Helm"
        echo "4. Verify Deployment"
        echo "5. Get Access Information"
        echo "6. Create Admin User"
        echo "7. Run Security Scan"
        echo "8. Show Logs"
        echo "9. Cleanup/Delete"
        echo "0. Exit"
        echo ""
        read -p "Select option: " OPTION
        
        case $OPTION in
            1)
                check_prerequisites
                build_image
                deploy_with_helm
                verify_deployment
                get_access_info
                ;;
            2)
                build_image
                ;;
            3)
                check_prerequisites
                deploy_with_helm
                ;;
            4)
                verify_deployment
                ;;
            5)
                get_access_info
                ;;
            6)
                create_admin_user
                ;;
            7)
                run_trivy_scan
                ;;
            8)
                show_logs
                ;;
            9)
                cleanup
                ;;
            0)
                echo "Goodbye!"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                ;;
        esac
    done
}

# Check if running with arguments
if [ $# -eq 0 ]; then
    main_menu
else
    case $1 in
        deploy)
            check_prerequisites
            build_image
            deploy_with_helm
            verify_deployment
            get_access_info
            ;;
        cleanup)
            cleanup
            ;;
        verify)
            verify_deployment
            ;;
        logs)
            show_logs
            ;;
        *)
            echo "Usage: $0 [deploy|cleanup|verify|logs]"
            echo "Or run without arguments for interactive menu"
            exit 1
            ;;
    esac
fi
