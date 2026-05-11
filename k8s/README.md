# Kubernetes manifests

Three manifests that deploy the plastic-detection API to a K8s cluster.

| File | Resource | Purpose |
|---|---|---|
| `namespace.yaml` | `Namespace` | Isolates this app from anything else in the cluster |
| `deployment.yaml` | `Deployment` | 2 replicas of the API container, with resource limits + probes |
| `service.yaml` | `Service` (NodePort) | Exposes the API on port 30080 of every node |

## Apply

Once `kubectl` is pointed at your cluster:

```bash
kubectl apply -f k8s/
```

Verify:

```bash
kubectl get all -n plastic-detection
kubectl get pods -n plastic-detection -w   # watch for Running + Ready 1/1
```

Pods take ~1-2 min to reach `Ready` because the readiness probe waits for the
YOLO model to load into memory (`/ready` returns 503 until model is loaded).

## Test the API

From outside the cluster, via any node's external IP:

```bash
curl http://<any-node-public-ip>:30080/
curl http://<any-node-public-ip>:30080/ready
```

## Resource limits

Per the assignment rubric, each pod is capped at:
- **CPU**: 1.0 vCPU (`limits.cpu: 1000m`)
- **Memory**: 2 GiB (sized to fit YOLOv8m + overhead)

## Scaling

```bash
kubectl scale deployment/plastic-detection-api -n plastic-detection --replicas=3
```

Or edit `replicas:` in `deployment.yaml` and re-apply.
