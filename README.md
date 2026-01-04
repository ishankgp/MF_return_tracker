# 📈 Mutual Fund Returns Tracker

A modern web application to track and analyze mutual fund performance with real-time data fetching, beautiful UI, and automated daily updates.

![Fund Performance Dashboard](screenshots/frontend_table.jpg)

## ✨ Features

- **Real-time Data Fetching**: Automatically fetches latest NAV and returns data from mutual fund APIs
- **Clean Web Interface**: Responsive UI built with Flask and modern web technologies
- **Smart Caching**: Redis-backed caching with in-memory fallback for optimal performance
- **Advanced Filtering**: Search and filter funds by name or category
- **Export Functionality**: Download fund data as CSV for further analysis
- **Auto-refresh**: Scheduled daily updates at 11 AM (configurable)
- **Performance Tracking**: Track returns across multiple timeframes (1D, 1W, 1M, 3M, 6M, 1Y, 3Y, 5Y)

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ 
- Redis (optional, for caching)

### One-Click Setup & Run

Simply double-click the startup script:

**`start.bat`**: Checks dependencies and starts the Flask server

Or run from command line:
```bash
.\start.bat
```

This will:
- Create virtual environment (if needed)
- Install Python dependencies
- Start the Flask server at http://localhost:5000
- Automatically open your browser

## 📦 Manual Installation

### Backend Setup

1. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run Flask server:
```bash
python app.py
```

The application will be available at http://localhost:5000

## 📁 Project Structure

```
mutual_funds/
├── app.py                    # Flask backend server
├── fetch_mf_returns.py       # Data fetching logic
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── start.bat                 # One-click launcher
├── templates/                # Flask HTML templates
├── static/                   # Static assets (CSS, JS)
└── logs/                     # Application logs
```

## 🔧 Configuration

### Adding/Modifying Funds

Edit the `funds` list in `fetch_mf_returns.py`:

```python
funds = [
    {"name": "Fund Name", "code": "FUND_CODE"},
    # Add more funds here
]
```

### Setting up Daily Auto-refresh (11 AM)

#### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 11:00 AM
4. Set action: Start `start.bat` (full path: `D:\Github clones\mutual_funds\start.bat`)
5. Enable "Run whether user is logged on or not"
6. Set "Start in" directory to: `D:\Github clones\mutual_funds`

#### Or use PowerShell to create scheduled task:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\Github clones\mutual_funds\start.bat" -WorkingDirectory "D:\Github clones\mutual_funds"
$trigger = New-ScheduledTaskTrigger -Daily -At 11:00AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "MutualFundTracker" -Action $action -Trigger $trigger -Settings $settings -Description "Daily mutual fund data refresh at 11 AM"
```

## 🔍 API Endpoints

- `GET /` - Main dashboard (web UI)
- `GET /api/funds` - Get all fund data (JSON)
- `POST /api/refresh` - Force data refresh
- `GET /health` - Health check endpoint

## 💡 Usage Tips

1. **Quick Search**: Use the search bar to find specific funds instantly
2. **Category Filter**: Filter by Large Cap, Mid Cap, Small Cap, Liquid, or Debt funds
3. **Sort Columns**: Click any column header to sort by that metric
4. **Export Data**: Click the download button to export current view as CSV
5. **View Details**: Click any fund row to see detailed performance metrics

## 🛠️ Troubleshooting

### Server won't start
- Ensure Python 3.8+ is installed: `python --version`
- Check if port 5000 is free: `netstat -an | findstr :5000`
- Verify all dependencies: `pip install -r requirements.txt`

### Data not updating
- Check internet connection
- Verify mutual fund API is accessible
- Clear Redis cache (if using): `redis-cli FLUSHALL`
- Check logs in `logs/app.log`

## 🔐 Environment Variables

Create a `.env` file for custom configuration:

```env
FLASK_ENV=development
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
```

## 📊 Performance

- **Caching**: 10-minute TTL for fund data
- **Async fetching**: Parallel API calls for faster data retrieval
- **Optimized rendering**: Efficient data handling for large datasets

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with Flask and modern web technologies
- Uses public mutual fund APIs for data
- Redis for high-performance caching

---

**Note**: This application is for educational and personal use. Always verify financial data from official sources before making investment decisions.