# Migration from Serverless Framework to AWS SAM

This document details the migration from Serverless Framework to AWS SAM (Serverless Application Model).

## Overview

The migration was completed to:
- Simplify deployment with native AWS tooling
- Improve CloudFormation integration
- Add automated CI/CD with GitHub Actions
- Reduce dependencies on third-party plugins
- Leverage better AWS ecosystem support

## Changes Made

### 1. Infrastructure as Code

**Before (Serverless Framework):**
```yaml
# serverless.yml
service: daily-nyt
org: mrteale
app: web-services

plugins:
  - serverless-python-requirements
  - serverless-domain-manager

provider:
  name: aws
  runtime: python3.9
  stage: prod
```

**After (AWS SAM):**
```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Daily NYT - Serverless application

Globals:
  Function:
    Timeout: 30
    MemorySize: 512
    Runtime: python3.9
```

### 2. Lambda Function Definition

**Before:**
```yaml
functions:
  main:
    handler: handler.main
    role: NYTIAMRole
    layers:
      - { Ref: PopplerLambdaLayer }
    events:
      - http:
          path: /
          method: get
          cors: true
```

**After:**
```yaml
Resources:
  MainFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: daily-nyt-main
      CodeUri: .
      Handler: handler.main
      Role: !GetAtt NYTIAMRole.Arn
      Layers:
        - !Ref PopplerLayer
      Events:
        GetNYT:
          Type: Api
          Properties:
            RestApiId: !Ref DailyNYTApi
            Path: /
            Method: get
```

### 3. API Gateway Configuration

**Before:**
- Configured through Serverless Framework abstractions
- Binary media types: `binaryMediaTypes: ['*/*']`
- CORS handled automatically

**After:**
- Explicit AWS::Serverless::Api resource
- Binary media types: `'*~1*'` (CloudFormation encoding)
- CORS configured explicitly:
  ```yaml
  Cors:
    AllowMethods: "'GET,OPTIONS'"
    AllowHeaders: "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    AllowOrigin: "'*'"
  ```

### 4. Lambda Layers

**Before:**
```yaml
layers:
  poppler:
    package:
      artifact: layers/poppler.zip
```

**After:**
```yaml
PopplerLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: daily-nyt-poppler
    Description: Poppler PDF processing library
    ContentUri: layers/poppler.zip
    CompatibleRuntimes:
      - python3.9
    RetentionPolicy: Retain
```

### 5. Custom Domain

**Before (using serverless-domain-manager plugin):**
```yaml
custom:
  customDomain:
    domainName: nyt.lachlanteale.com
    basePath: ''
    stage: ${self:provider.stage}
    createRoute53Record: false
```

**After (native API Gateway domain):**
```yaml
Domain:
  DomainName: nyt.lachlanteale.com
  CertificateArn: !Ref DomainCertificateArn
  EndpointConfiguration: EDGE
  Route53:
    HostedZoneId: !Ref HostedZoneId
```

### 6. CI/CD Pipeline

**Before:**
- Manual deployments only
- No automated testing
- `serverless deploy` command

**After:**
- GitHub Actions workflow (`.github/workflows/deploy.yml`)
- Automated deployment on push to master/main
- SAM validation and build steps
- Deployment summary in GitHub UI

### 7. Package Management

**Before (package.json):**
```json
{
  "dependencies": {
    "serverless": "^4.1.12",
    "serverless-apigw-binary": "^0.4.4",
    "serverless-domain-manager": "^6.0.3"
  },
  "devDependencies": {
    "serverless-python-requirements": "^6.1.0"
  }
}
```

**After (package.json):**
```json
{
  "name": "daily-nyt",
  "scripts": {
    "validate": "sam validate --lint",
    "build": "sam build",
    "deploy": "sam deploy",
    "local:api": "sam local start-api",
    "logs": "sam logs -n MainFunction --tail"
  }
}
```

### 8. Configuration Files

**New Files Added:**
- `template.yaml` - SAM template (replaces serverless.yml)
- `samconfig.toml` - SAM CLI configuration
- `.github/workflows/deploy.yml` - GitHub Actions workflow
- `MIGRATION.md` - This migration guide

**Files Modified:**
- `package.json` - Updated scripts and removed Serverless dependencies
- `.gitignore` - Added SAM-specific entries
- `README.md` - Updated documentation

**Files Deprecated (can be removed after successful migration):**
- `serverless.yml` - Replaced by template.yaml
- `node_modules/` - Serverless Framework and plugins no longer needed

## Lambda Function Performance Improvements

The SAM template includes performance improvements:

**Before:**
- Memory: 128 MB (default)
- Timeout: 6 seconds (default)

**After:**
- Memory: 512 MB (increased for faster PDF processing)
- Timeout: 30 seconds (more time for PDF download and conversion)

## Deployment Comparison

### Serverless Framework

```bash
# Install dependencies
npm install

# Deploy
serverless deploy

# View logs
serverless logs -f main -t
```

### AWS SAM

```bash
# Build
sam build --use-container

# Deploy
sam deploy

# View logs
sam logs -n MainFunction --stack-name daily-nyt-prod --tail
```

## GitHub Actions Setup

To enable automated deployments, configure these GitHub secrets:

### Option 1: OIDC (Recommended)

1. Create an IAM OIDC identity provider for GitHub
2. Create an IAM role with appropriate permissions
3. Add `AWS_ROLE_ARN` secret to GitHub repository

### Option 2: Access Keys

1. Create an IAM user with programmatic access
2. Add these secrets to GitHub repository:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

## Post-Migration Checklist

- [ ] Validate SAM template: `sam validate --lint`
- [ ] Build application: `sam build --use-container`
- [ ] Test locally: `sam local start-api`
- [ ] Deploy to AWS: `sam deploy --guided`
- [ ] Verify API endpoint works
- [ ] Test custom domain (if configured)
- [ ] Set up GitHub secrets for CI/CD
- [ ] Test GitHub Actions deployment
- [ ] Update DNS records if needed
- [ ] Remove old Serverless Framework files
- [ ] Update team documentation

## Rollback Plan

If you need to rollback to Serverless Framework:

1. The original `serverless.yml` is still in the repository
2. Reinstall Serverless dependencies: `npm install`
3. Deploy with Serverless: `serverless deploy`
4. Delete SAM stack: `sam delete --stack-name daily-nyt-prod`

## Benefits of Migration

1. **Better AWS Integration**: Native CloudFormation support
2. **Simplified Tooling**: No need for third-party plugins
3. **Improved CI/CD**: GitHub Actions for automated deployments
4. **Enhanced Monitoring**: Better CloudFormation stack management
5. **Cost Visibility**: Direct CloudFormation stack cost tracking
6. **Team Adoption**: SAM is widely adopted in AWS ecosystem

## Resources

- [AWS SAM Documentation](https://docs.aws.amazon.com/serverless-application-model/)
- [SAM CLI Reference](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)
- [GitHub Actions for AWS](https://github.com/aws-actions)

## Support

For issues or questions about this migration:
- Check the [README.md](README.md) for usage instructions
- Review CloudFormation stack events for deployment issues
- Check Lambda logs for runtime issues
