# Databricks Workspace Setup

Created via AWS Marketplace subscription.

## Workspace

| | |
|---|---|
| Region | us-east-1 |
| Workspace URL | |
| Account ID | |

## AWS Resources Created by Databricks

| Resource | Name |
|---|---|
| Workspace assets S3 bucket | databricks-tiqgwrgmhhmhrhkrcf3ptz-cloud-storage-bucket |
| IAM role — workspace storage | databricks-tiqgwrgmhhmhrhkrcf3ptz-cloud-storage-role |
| IAM role — compute (cross-account) | databricks-tiqgwrgmhhmhrhkrcf3ptz-cross-account-role |

## Post-Setup Steps

- [ ] Register instance profile ARN (from Terraform output) in workspace: Settings → Security → Instance profiles
- [ ] Add Databricks provider to Terraform and apply (secret scope, secret for Google Maps API key)
- [ ] Upload `scripts/install_chrome.sh` to workspace: Workspace → /Shared/property-data-platform/
- [ ] Add GitHub Actions secrets: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `S3_BUCKET`, `INSTANCE_PROFILE_ARN`
- [ ] Run `databricks bundle deploy -t prod`
