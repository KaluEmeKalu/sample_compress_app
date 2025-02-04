# Deployment Guide for Summit API on DigitalOcean App Platform

This guide provides detailed steps to deploy the Summit API PDF compression service on DigitalOcean App Platform.

## Prerequisites

1. A DigitalOcean account
2. Your code pushed to a GitHub repository
3. (Optional) DigitalOcean CLI (doctl) installed

## Deployment Steps

### Option 1: Using DigitalOcean Console (Recommended for first deployment)

1. **Login to DigitalOcean**
   - Go to [DigitalOcean Cloud Console](https://cloud.digitalocean.com/)
   - Sign in to your account

2. **Create a New App**
   - Click on "Apps" in the left sidebar
   - Click "Create App"
   - Select "GitHub" as your source
   - Select your repository and branch
   - Click "Next"

3. **Configure Your App**
   - Edit the app name if desired
   - Select the closest region to your users
   - Keep the "Autodeploy" option enabled
   - Click "Next"

4. **Configure Environment Variables**
   Add the following environment variables:
   ```
   DJANGO_SECRET_KEY=[Generate a secure secret key]
   DJANGO_DEBUG=False
   ```
   Note: DJANGO_ALLOWED_HOSTS will be automatically configured by DigitalOcean

5. **Review and Launch**
   - Review your app configuration
   - Click "Create Resources"
   - Wait for the build and deployment to complete

### Option 2: Using doctl CLI

1. **Install doctl**
   ```bash
   # For macOS
   brew install doctl

   # For other systems, visit:
   # https://docs.digitalocean.com/reference/doctl/how-to/install/
   ```

2. **Authenticate doctl**
   ```bash
   doctl auth init
   ```
   Follow the prompts to enter your API token

3. **Deploy the App**
   ```bash
   doctl apps create --spec .do/app.yaml
   ```

4. **Monitor Deployment**
   ```bash
   doctl apps list
   doctl apps get [APP_ID]
   ```

## Post-Deployment Configuration

1. **Set Up Custom Domain (Optional)**
   - Go to your app's settings in the DigitalOcean console
   - Click on "Domains"
   - Add your custom domain
   - Follow the DNS configuration instructions

2. **Configure SSL/TLS**
   - SSL/TLS is automatically configured by DigitalOcean App Platform
   - No additional steps required

3. **Monitor Your App**
   - Go to your app's dashboard
   - Check the "Monitoring" tab for:
     - CPU usage
     - Memory usage
     - Request count
     - Response times

## Scaling

1. **Vertical Scaling**
   - Go to your app's "Settings"
   - Click on "Edit Plan"
   - Choose a larger instance size

2. **Horizontal Scaling**
   - Go to your app's "Settings"
   - Click on "Edit Plan"
   - Adjust the number of instances

## Troubleshooting

1. **Check Logs**
   - Go to your app's dashboard
   - Click on "Logs"
   - Review the application logs for errors

2. **Common Issues**
   - If static files aren't serving: Ensure STATIC_ROOT is correctly set
   - If deployment fails: Check the build logs
   - If app crashes: Check the runtime logs

## Maintenance

1. **Updates and Deployments**
   - Push changes to your GitHub repository
   - App Platform will automatically rebuild and deploy

2. **Database Backups**
   - Currently using SQLite, consider migrating to DigitalOcean Managed Database for production

3. **Monitoring**
   - Regularly check the "Monitoring" tab
   - Set up alerts for unusual patterns

## Security Notes

1. Ensure DJANGO_SECRET_KEY is secure and unique
2. Keep DEBUG=False in production
3. Regularly update dependencies
4. Monitor the security alerts in your GitHub repository

## Cost Optimization

1. Start with the Basic plan
2. Monitor usage patterns
3. Scale up only when needed
4. Consider using the App Platform dev plan for development/staging environments

## Support

For issues with:
- App Platform: Contact DigitalOcean support
- Application code: Create an issue in the GitHub repository