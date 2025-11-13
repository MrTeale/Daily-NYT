# Daily-NYT

A serverless application that fetches and converts the New York Times front page to JPEG format using AWS SAM (Serverless Application Model).

## Architecture

This application uses:
- **AWS Lambda** (Python 3.9) - Fetches NYT front page PDF and converts to JPEG
- **API Gateway** - REST API endpoint for accessing the Lambda function
- **Lambda Layer** - Poppler library for PDF processing
- **Custom Domain** - nyt.lachlanteale.com

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html))
- Python 3.9
- Docker (for building with --use-container)

## Local Development

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Build the Application

```bash
# Build locally
sam build

# Or build using Docker (recommended for consistent builds)
sam build --use-container
```

### Test Locally

```bash
# Start local API Gateway
sam local start-api

# Invoke function directly
sam local invoke MainFunction
```

### Validate Template

```bash
sam validate --lint
```

## Deployment

### Automated Deployment (GitHub Actions)

The application automatically deploys to AWS when code is pushed to the `master` or `main` branch.

**Required GitHub Secrets:**
- `AWS_ROLE_ARN` - ARN of IAM role for OIDC authentication (recommended)

**OR**

- `AWS_ACCESS_KEY_ID` - AWS Access Key
- `AWS_SECRET_ACCESS_KEY` - AWS Secret Key

### Manual Deployment

```bash
# Deploy using default configuration
sam deploy

# Deploy with guided prompts (first time)
sam deploy --guided

# Deploy to production environment
npm run deploy:prod
```

### NPM Scripts

```bash
npm run validate          # Validate SAM template
npm run build            # Build application locally
npm run build:container  # Build using Docker
npm run deploy           # Deploy to AWS
npm run deploy:prod      # Deploy to production
npm run deploy:guided    # Deploy with guided setup
npm run local:api        # Start local API Gateway
npm run local:invoke     # Invoke function locally
npm run logs             # Tail Lambda logs
npm run delete           # Delete CloudFormation stack
```

## API Endpoint

**Production URL:** https://nyt.lachlanteale.com/

**Method:** GET

**Response:** Base64-encoded JPEG image of the NYT front page

### Example Usage

```bash
curl https://nyt.lachlanteale.com/ | base64 -d > nyt_frontpage.jpg
```

## Project Structure

```
Daily-NYT/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions workflow
├── layers/
│   └── poppler.zip            # Poppler PDF library Lambda Layer
├── handler.py                  # Lambda function code
├── requirements.txt            # Python dependencies
├── template.yaml              # SAM template (CloudFormation)
├── samconfig.toml            # SAM CLI configuration
└── package.json              # NPM scripts and metadata
```

## Configuration

### Custom Domain Setup

To use a custom domain, you need to:

1. Have an ACM certificate in the same region as your API
2. Configure the following parameters in `template.yaml`:
   - `DomainCertificateArn` - ARN of your ACM certificate
   - `HostedZoneId` - Route53 Hosted Zone ID

Or update the template to remove the custom domain configuration.

### Environment Variables

Lambda environment variables can be configured in `template.yaml` under `Globals.Function.Environment.Variables`.

## Monitoring

View Lambda logs:

```bash
# Tail logs in real-time
npm run logs

# View logs in AWS CloudWatch Console
aws logs tail /aws/lambda/daily-nyt-main --follow
```

## Migration from Serverless Framework

This project was migrated from Serverless Framework to AWS SAM. Key changes:

- `serverless.yml` → `template.yaml` (SAM template)
- Removed Serverless Framework plugins
- Added GitHub Actions for CI/CD
- Simplified deployment process
- Better CloudFormation integration

## Troubleshooting

### Build Issues

If you encounter build issues, try using Docker:

```bash
sam build --use-container
```

### Deployment Issues

Check CloudFormation stack events:

```bash
aws cloudformation describe-stack-events --stack-name daily-nyt-prod
```

### Lambda Issues

Check Lambda logs:

```bash
npm run logs
```

## License

See [LICENSE.txt](LICENSE.txt) for details.

## Author

MrTeale
