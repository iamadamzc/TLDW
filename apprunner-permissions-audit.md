# AppRunnerInstanceRole Permission Audit

## Role: AppRunnerInstanceRole
**ARN:** arn:aws:iam::528131355234:role/AppRunnerInstanceRole
**Trusted Entity:** tasks.apprunner.amazonaws.com ✅

## Inline Policies (3 total)

### 1. AppRunnerSecretsAccess
**Status:** ✅ UPDATED
**Permissions:**
- `secretsmanager:GetSecretValue` on `TLDW-*` and `tldw-*` secrets
- **Recently fixed:** Added wildcard to allow all TLDW secrets including Google OAuth

### 2. AppRunnerCookieAccess
**Status:** ⏳ NEEDS VERIFICATION
**Expected permissions:**
- Should allow reading/writing to cookie storage (S3 or local)

### 3. CookieS3Access
**Status:** ⏳ NEEDS VERIFICATION
**Expected permissions:**
- S3 bucket: `tldw-cookies-bucket`
- Actions: s3:GetObject, s3:PutObject, s3:DeleteObject

## Required Permissions Summary

For the TLDW app to work fully, AppRunnerInstanceRole needs:

1. ✅ **Secrets Manager** - Read all TLDW-* secrets (FIXED)
2. ⏳ **S3 Cookie Bucket** - Read/write cookies to tldw-cookies-bucket
3. ⏳ **ECR** - Pull Docker images (handled by access role, not instance role)
4. ⏳ **CloudWatch Logs** - Write application logs (usually automatic)

## Next Steps

1. Verify S3 bucket permissions
2. Restart App Runner deployment to pick up updated IAM policy
3. Test OAuth login
4. Monitor logs for any permission errors
