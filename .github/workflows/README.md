# CI/CD Pipeline Documentation

This directory contains the GitHub Actions workflow files for the Stock Scanner application's CI/CD pipeline.

## Overview

The CI/CD pipeline automates the testing, building, and (eventually) deployment of the Stock Scanner application. It helps ensure code quality and reduces the risk of introducing bugs.

## Workflows

### `ci.yml`

This workflow is triggered on pushes and pull requests to the main, master, and develop branches. It consists of the following jobs:

#### Backend Tests

- Runs the backend tests using Docker Compose
- Creates a temporary `.env` file with test values
- Uses the existing `docker-compose.test.yml` file
- Fails if any tests fail

#### Frontend Linting

- Sets up Node.js
- Installs frontend dependencies
- Runs the linting script to check code quality

#### Build Images

- Builds the Docker images for production
- Uses GitHub Actions cache for faster builds
- Doesn't push the images to a registry (this can be added later)

#### Deploy (Commented Out)

- A placeholder for future deployment steps
- Only runs on the main or master branch
- Depends on the successful completion of the build-images job

## How to Use

### Local Testing

Before pushing your changes, you can run the tests locally using:

```bash
# For backend tests
./run-tests.sh  # On Linux/macOS
run-tests.bat   # On Windows

# For frontend linting
cd frontend
npm run lint
```

### CI/CD Pipeline Status

You can check the status of the CI/CD pipeline in the "Actions" tab of the GitHub repository.

### Troubleshooting

If the CI/CD pipeline fails, check the following:

1. **Backend Tests**: Look at the test logs to see which tests failed and why.
2. **Frontend Linting**: Check the linting errors and fix them according to the project's style guide.
3. **Build Images**: Ensure that the Dockerfiles are correct and that all dependencies are properly specified.

## Future Improvements

- Add frontend tests
- Implement code coverage reporting
- Add security scanning
- Configure automatic deployment to staging/production environments
- Set up notifications for pipeline failures