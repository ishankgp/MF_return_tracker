# 📈 Mutual Fund Returns Tracker

A modern web application to track and analyze mutual fund performance with real-time data fetching, beautiful UI, and automated daily updates.

![Fund Performance Dashboard](screenshots/frontend_table.jpg)

## ✨ Features

- **Real-time Data Fetching**: Automatically fetches latest NAV and returns data from mutual fund APIs
- **Modern React Frontend**: Clean, responsive UI built with Next.js and Tailwind CSS
- **Smart Caching**: Redis-backed caching with in-memory fallback for optimal performance
- **Advanced Filtering**: Search and filter funds by name or category
- **Interactive Details**: Click any fund to see detailed performance metrics and charts
- **Export Functionality**: Download fund data as CSV for further analysis
- **Notes Management**: Add, edit, and delete personal notes about funds
- **Auto-refresh**: Scheduled daily updates at 11 AM (configurable)
- **Performance Tracking**: Track returns across multiple timeframes (1D, 1W, 1M, 3M, 6M, 1Y, 3Y, 5Y)

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ 
- Node.js 16+
- Redis (optional, for caching)

### One-Click Setup & Run

Simply double-click the `quick-start.bat` file to launch both backend and frontend automatically.

Or run from command line:
```bash
.\quick-start.bat
```

This will:
- Start the Flask backend at http://127.0.0.1:5000
- Start the Next.js frontend at http://localhost:3000
- Open your browser automatically

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

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd v0-mf-return-tracker-frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run development server:
```bash
npm run dev
```

## 📁 Project Structure

```
mutual_funds/
├── app.py                    # Flask backend server
├── fetch_mf_returns.py       # Data fetching logic
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── quick-start.bat          # One-click launcher
├── start-mf-tracker.bat     # Backend starter with checks
├── v0-mf-return-tracker-frontend/
│   ├── app/                 # Next.js app directory
│   │   ├── page.tsx         # Main dashboard page
│   │   └── api/             # API routes
│   ├── components/          # React components
│   │   ├── fund-details-dialog.tsx
│   │   ├── notes-section.tsx
│   │   └── ui/              # Reusable UI components
│   ├── services/            # API service layer
│   └── package.json         # Node dependencies
├── templates/               # Flask HTML templates
├── static/                  # Static assets
└── logs/                    # Application logs
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
4. Set action: Start `quick-start.bat`
5. Enable "Run whether user is logged on or not"

#### Or use PowerShell to create scheduled task:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\Github clones\mutual_funds\quick-start.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 11:00AM
Register-ScheduledTask -TaskName "MutualFundTracker" -Action $action -Trigger $trigger
```

## 🔍 API Endpoints

### Backend (Flask)

- `GET /` - Main dashboard (HTML)
- `GET /api/funds` - Get all fund data (JSON)
- `POST /api/refresh` - Force data refresh
- `GET /health` - Health check endpoint

### Frontend API Routes

- `GET /api/funds` - Proxies to Flask backend
- `POST /api/refresh` - Triggers data refresh

## 💡 Usage Tips

1. **Quick Search**: Use the search bar to find specific funds instantly
2. **Category Filter**: Filter by Large Cap, Mid Cap, Small Cap, Liquid, or Debt funds
3. **Sort Columns**: Click any column header to sort by that metric
4. **Export Data**: Click the download button to export current view as CSV
5. **Add Notes**: Use the Notes section to track your observations
6. **View Details**: Click any fund row to see detailed performance charts

## 🛠️ Troubleshooting

### Backend won't start
- Ensure Python 3.8+ is installed: `python --version`
- Check if port 5000 is free: `netstat -an | findstr :5000`
- Verify all dependencies: `pip install -r requirements.txt`

### Frontend won't start
- Ensure Node.js 16+ is installed: `node --version`
- Clear npm cache: `npm cache clean --force`
- Reinstall dependencies: `rm -rf node_modules && npm install`

### Data not updating
- Check internet connection
- Verify mutual fund API is accessible
- Clear Redis cache (if using): `redis-cli FLUSHALL`
- Check logs in `logs/app.log`

### CORS errors
- Ensure backend is running on http://127.0.0.1:5000
- Check CORS is enabled in `app.py`

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
- **Optimized rendering**: React memo and virtualization for large datasets
- **Lazy loading**: Components load on-demand

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with Flask, Next.js, and Tailwind CSS
- Uses public mutual fund APIs for data
- Redis for high-performance caching
- shadcn/ui for beautiful components

---

**Note**: This application is for educational and personal use. Always verify financial data from official sources before making investment decisions.