# Mutual Fund Returns Tracker - Optimized

A high-performance web application for tracking mutual fund returns with real-time data fetching and intelligent caching.

## 🚀 Key Optimizations

### Performance Improvements
- **Smart Dependency Checking**: Batch file now only installs dependencies when needed
- **Enhanced Caching**: Increased cache TTL from 5 to 10 minutes for better performance
- **Improved Rate Limiting**: Increased from 2 to 3 requests per second
- **Better Connection Pooling**: Optimized HTTP connection settings
- **Memory Cache Optimization**: Increased cache size and TTL

### Code Optimizations
- **Centralized Configuration**: All settings in `config.py`
- **Better Error Handling**: Comprehensive error handling throughout
- **Improved Logging**: Structured logging with file rotation
- **Production Ready**: Docker and Gunicorn support

## 📦 Installation & Usage

### Quick Start (Development)
```bash
# Run the optimized batch file
start-mf-tracker.bat
```

### Production Deployment
```bash
# Using Docker Compose (recommended for Linux/macOS)
docker-compose up -d

# Using production batch file (Windows-compatible)
start-production.bat

# Or run the production server directly
python production_server.py
```

### Manual Setup
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies (only if needed)
pip install -r requirements.txt

# Run the application
python app.py
```

## 🏗️ Architecture

### Backend (Flask)
- **Async Data Fetching**: Uses aiohttp for concurrent API calls
- **Multi-level Caching**: Redis + in-memory cache
- **Rate Limiting**: Prevents API abuse
- **Health Monitoring**: Built-in health checks
- **Cross-Platform**: Windows-compatible with Waitress server

### Frontend (Next.js)
- **Modern UI**: Built with Tailwind CSS and shadcn/ui
- **Real-time Updates**: Auto-refresh functionality
- **Responsive Design**: Mobile-friendly interface

## 🔧 Configuration

### Environment Variables
```bash
# Flask Settings
FLASK_ENV=development|production
DEBUG=True|False
SECRET_KEY=your-secret-key

# Redis Settings
REDIS_URL=redis://localhost:6379
REDIS_TTL=600

# API Settings
API_TIMEOUT=15
API_RATE_LIMIT=3
API_RATE_PERIOD=1

# Performance Settings
MAX_CONCURRENT_REQUESTS=10
CONNECTION_POOL_SIZE=5
```

### Cache Configuration
- **Memory Cache**: 200 items, 10-minute TTL
- **Redis Cache**: 10-minute TTL (if available)
- **API Cache**: 10-minute TTL per fund

## 📊 Performance Metrics

### Before Optimization
- Dependencies installed every startup
- 5-minute cache TTL
- 2 requests/second rate limit
- Basic error handling

### After Optimization
- Smart dependency checking
- 10-minute cache TTL
- 3 requests/second rate limit
- Comprehensive error handling
- Production-ready deployment

## 🐳 Docker Deployment

### Build and Run
```bash
# Build the image
docker build -t mf-tracker .

# Run with Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f app
```

### Health Checks
- Application: `http://localhost:5000/health`
- Redis: Automatic health monitoring

## 📈 Monitoring

### Health Endpoint
```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "redis_connected": true,
  "funds_count": 9,
  "cache_size": 9
}
```

### Log Files
- Application logs: `logs/app.log`
- Production logs: `logs/production.log`
- Performance metrics: `logs/performance_metrics.json`

## 🔄 API Endpoints

- `GET /` - Main dashboard
- `GET /api/funds` - Fund data API
- `GET /api/refresh` - Force data refresh
- `GET /health` - Health check
- `GET /favicon.ico` - Favicon

## 🛠️ Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Quality
```bash
# Install linting tools
pip install flake8 black

# Format code
black .

# Lint code
flake8 .
```

## 📝 Changelog

### v2.0.0 - Optimization Release
- ✅ Smart dependency installation
- ✅ Enhanced caching strategy
- ✅ Improved performance
- ✅ Production deployment support
- ✅ Docker containerization
- ✅ Comprehensive monitoring
- ✅ Better error handling

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the health endpoint
2. Review the logs
3. Open an issue on GitHub

---

**Note**: The batch file now only installs dependencies when they're missing, significantly reducing startup time on subsequent runs.