# ArgoCD Setup

Quick notes on the ArgoCD configs for this project.

## What's here

Two environments:
- **prod** (`subscription-tracker-prod.yaml`) - runs off main branch, 2 replicas
- **dev** (`subscription-tracker-dev.yaml`) - runs off develop branch, 1 replica

Both pull from the helm chart in `helm-charts/subscription-tracker`.

## Deploying

Apply them:
```bash
kubectl apply -f argocd/subscription-tracker-prod.yaml
kubectl apply -f argocd/subscription-tracker-dev.yaml
```

Or just do everything at once:
```bash
kubectl apply -f argocd/
```

## Checking status

Web UI is at https://192.168.223.91:32572

Or via CLI:
```bash
kubectl get applications -n argocd
argocd app get subscription-tracker-prod
```

## Auto-sync is on

Both apps auto-sync, so changes in git get deployed automatically. They also self-heal (manual cluster changes get reverted) and auto-prune (deleted stuff in git gets deleted in cluster).

Turn it off if needed:
```bash
argocd app set subscription-tracker-prod --sync-policy none
```

## Manual sync

Force a sync:
```bash
argocd app sync subscription-tracker-prod
```

## Deleting

Remove the ArgoCD app (keeps resources running):
```bash
kubectl delete -f argocd/subscription-tracker-prod.yaml
```

Remove everything:
```bash
kubectl delete application subscription-tracker-prod -n argocd
```

## Common issues

**Namespace stuck terminating**

Ran into this before - pods won't start with "namespace is being terminated" error. Fix:

```bash
# Check what's happening
sudo journalctl -u k3s --since "5 minutes ago" | grep -i "subscription-tracker"

# Force delete it
kubectl delete namespace subscription-tracker --force --grace-period=0

# Recreate if needed
kubectl create namespace subscription-tracker
```

ArgoCD will sync everything back automatically.

**Pod problems**

```bash
kubectl get pods -n subscription-tracker -o wide
kubectl logs -f deployment/flask-app -n subscription-tracker
kubectl describe pod <pod-name> -n subscription-tracker
```

**Is it actually working?**

```bash
curl http://192.168.223.30/health
```
