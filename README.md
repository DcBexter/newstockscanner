# Stock Scanner Application

## Project Components

The application consists of four main components:

1. **Scraper Service**: Periodically scrapes websites for new stock listings and saves them to the database
2. **Notification Service**: Sends notifications about new listings via Telegram
3. **API Service**: Provides REST API endpoints for the frontend
4. **Frontend**: Web interface for users to view and interact with the data

## Project Structure

```
/
├── backend/                # Backend services
│   ├── Dockerfile.dev      # Backend Docker configuration for development
│   ├── Dockerfile.prod     # Backend Docker configuration for production
│   ├── requirements.txt    # Python dependencies
│   ├── database/           # Database related files
│   │   └── init.sql        # Database initialization script
│   ├── core/               # Shared core functionality
│   │   ├── models.py
│   │   ├── exceptions.py
│   │   └── utils.py
│   ├── config/             # Shared configuration
│   │   ├── settings.py
│   │   └── logging.py
│   ├── database/           # Database models and session management
│   │   ├── models.py
│   │   └── session.py
│   ├── scraper_service/    # Scraper service
│   │   ├── scrapers/       # Scrapers for different sources
│   │   └── scheduler.py    # Scheduler for periodic scraping
│   ├── notification_service/ # Notification service
│   │   ├── notifiers/      # Notification providers
│   │   └── service.py      # Notification service implementation
│   └── api_service/        # API service
│       ├── routes/         # API routes
│       └── app.py          # FastAPI application
│
├── frontend/              # Frontend application
│   ├── Dockerfile.dev     # Frontend Docker configuration for development
│   ├── Dockerfile.prod    # Frontend Docker configuration for production
│   ├── nginx/             # Nginx configuration
│   │   └── nginx.conf     # Nginx configuration file
│   ├── public/            # Static assets
│   └── src/               # React source code
│       ├── api/           # API client
│       ├── components/    # React components
│       └── assets/        # Frontend assets
│
├── docker-compose.yml     # Docker Compose configuration for production
├── docker-compose.dev.yml # Docker Compose configuration for development
├── start-dev.bat          # Script to start the application in development mode
├── start-prod.bat         # Script to start the application in production mode
└── .env                   # Environment variables
```

## Development and Production Environments

The application supports two environments: development and production.

### Development Environment
The development environment is designed for developers and includes:
- Hot reloading for both frontend and backend
- Volume mounts for live code updates
- Debug mode enabled
- Source maps and detailed error messages

To start the application in development mode:
```bash
./start-dev.bat  # On Windows
# or
docker-compose -f docker-compose.dev.yml up --build  # On any platform
```

The development frontend will be available at `http://localhost:5173`.

### Production Environment
The production environment is optimized for performance and security:
- Compiled frontend assets served by Nginx
- No hot reloading or volume mounts
- Optimized Docker images
- Non-root users for services

To start the application in production mode:
```bash
./start-prod.bat  # On Windows
# or
docker-compose up --build  # On any platform
```

The production frontend will be available at `http://localhost:80`.

## Progress Tracking

- [x] Initial directory structure created
- [x] Scraper service refactored
- [x] Notification service refactored
- [x] API service refactored
- [x] Frontend organization reviewed and moved to root level
- [x] Docker configuration updated and moved to appropriate directories
- [x] Development and production environments configured
- [ ] Application running successfully
