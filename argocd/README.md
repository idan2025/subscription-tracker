# ArgoCD Setup Guide

## Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl configured
- Helm 3 installed

## Install ArgoCD

### Step 1: Create ArgoCD namespace and install

```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available --timeout=600s deployment/argocd-server -n argocd
```

### Step 2: Access ArgoCD UI

```bash
# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

# Port forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Access UI at: https://localhost:8080
# Username: admin
# Password: <from above command>
```

### Step 3: Install ArgoCD CLI (Optional)

```bash
# Linux
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
rm argocd-linux-amd64

# macOS
brew install argocd

# Windows (using Chocolatey)
choco install argocd-cli
```

### Step 4: Login to ArgoCD

```bash
# Login via CLI
argocd login localhost:8080 --username admin --password <password> --insecure

# Change admin password (recommended)
argocd account update-password
```

## Deploy Subscription Tracker with ArgoCD

### Method 1: Using kubectl

```bash
# Apply the ArgoCD application manifest
kubectl apply -f argocd/application.yaml

# Check application status
kubectl get application -n argocd

# Watch sync progress
argocd app get subscription-tracker --refresh
```

### Method 2: Using ArgoCD UI

1. Login to ArgoCD UI
2. Click "+ NEW APP"
3. Fill in details:
   - **Application Name**: subscription-tracker
   - **Project**: default
   - **Sync Policy**: Automatic
   - **Repository URL**: https://github.com/idan2025/subscription-tracker
   - **Path**: helm-charts/subscription-tracker
   - **Cluster**: https://kubernetes.default.svc
   - **Namespace**: subscription-tracker
4. Click "CREATE"

### Method 3: Using ArgoCD CLI

```bash
argocd app create subscription-tracker \
  --repo https://github.com/idan2025/subscription-tracker.git \
  --path helm-charts/subscription-tracker \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace subscription-tracker \
  --sync-policy automated \
  --auto-prune \
  --self-heal
```

## Sync and Manage Application

### Manual Sync

```bash
# Sync application
argocd app sync subscription-tracker

# Hard refresh (ignore cache)
argocd app sync subscription-tracker --force

# Dry run
argocd app sync subscription-tracker --dry-run
```

### View Status

```bash
# Get application details
argocd app get subscription-tracker

# View application history
argocd app history subscription-tracker

# View application logs
argocd app logs subscription-tracker

# View resources
kubectl get all -n subscription-tracker
```

### Rollback

```bash
# List history
argocd app history subscription-tracker

# Rollback to specific revision
argocd app rollback subscription-tracker <revision-id>
```

## Configure Private Repository Access

If using a private Git repository:

```bash
# Add repository credentials
argocd repo add https://github.com/idan2025/subscription-tracker.git \
  --username <username> \
  --password <personal-access-token>

# Or using SSH
argocd repo add git@github.com:idan2025/subscription-tracker.git \
  --ssh-private-key-path ~/.ssh/id_rsa
```

## Expose ArgoCD Server (Production)

### Option 1: NodePort

```bash
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "NodePort"}}'
```

### Option 2: LoadBalancer

```bash
kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'
```

### Option 3: Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: argocd-server-ingress
  namespace: argocd
  annotations:
    nginx.ingress.kubernetes.io/ssl-passthrough: "true"
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
spec:
  ingressClassName: nginx
  rules:
  - host: argocd.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: argocd-server
            port:
              number: 443
  tls:
  - hosts:
    - argocd.yourdomain.com
    secretName: argocd-tls-secret
```

## ArgoCD Monitoring

### Sync Waves

Add annotations to resources for controlled deployment order:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"  # Deploy in wave 1
```

### Hooks

Add pre/post sync hooks:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/hook: PreSync  # Or PostSync, Sync, etc.
```

## Troubleshooting

### Application not syncing

```bash
# Check application health
argocd app get subscription-tracker

# View events
kubectl get events -n subscription-tracker --sort-by='.lastTimestamp'

# Check ArgoCD logs
kubectl logs -n argocd deployment/argocd-application-controller

# Force sync
argocd app sync subscription-tracker --force
```

### Image pull errors

```bash
# Create image pull secret
kubectl create secret docker-registry regcred \
  --docker-server=ghcr.io \
  --docker-username=<username> \
  --docker-password=<token> \
  -n subscription-tracker

# Reference in deployment
spec:
  imagePullSecrets:
  - name: regcred
```

## Useful Commands

```bash
# List all applications
argocd app list

# Delete application
argocd app delete subscription-tracker

# View application parameters
argocd app get subscription-tracker --show-params

# Update application
argocd app set subscription-tracker --parameter flask.replicaCount=3

# View application manifests
argocd app manifests subscription-tracker
```

## Best Practices

1. **Use GitOps**: Keep all configuration in Git
2. **Enable Auto-Sync**: For automatic deployments
3. **Use Sync Waves**: Control deployment order
4. **Add Health Checks**: Proper readiness/liveness probes
5. **Monitor Resources**: Use ArgoCD notifications
6. **Backup ArgoCD**: Backup ArgoCD configuration regularly

## Integration with CI/CD

Your GitHub Actions workflow automatically:
1. Builds and tests code
2. Scans with Trivy
3. Pushes image to registry
4. Updates image tag
5. ArgoCD detects change and syncs automatically

## Additional Resources

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [GitOps Guide](https://www.gitops.tech/)
- [ArgoCD Best Practices](https://argoproj.github.io/argo-cd/user-guide/best_practices/)
