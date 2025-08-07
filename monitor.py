#!/usr/bin/env python3
"""
Performance monitoring script for Mutual Fund Returns Tracker
"""

import requests
import time
import json
import psutil
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.metrics = []
    
    def check_health(self):
        """Check application health"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def check_api_performance(self):
        """Test API endpoint performance"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/api/funds", timeout=30)
            end_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "response_time": round((end_time - start_time) * 1000, 2),  # ms
                    "funds_count": len(data.get("funds", [])),
                    "status": "success"
                }
            else:
                return {
                    "response_time": round((end_time - start_time) * 1000, 2),
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "response_time": 0,
                "status": "error",
                "error": str(e)
            }
    
    def get_system_metrics(self):
        """Get system resource usage"""
        try:
            process = psutil.Process()
            return {
                "cpu_percent": round(process.cpu_percent(), 2),
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
                "memory_percent": round(process.memory_percent(), 2),
                "open_files": len(process.open_files()),
                "threads": process.num_threads()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}
    
    def run_monitoring_cycle(self):
        """Run a complete monitoring cycle"""
        timestamp = datetime.now().isoformat()
        
        # Check health
        health = self.check_health()
        
        # Check API performance
        api_perf = self.check_api_performance()
        
        # Get system metrics
        system = self.get_system_metrics()
        
        # Combine metrics
        cycle_metrics = {
            "timestamp": timestamp,
            "health": health,
            "api_performance": api_perf,
            "system": system
        }
        
        self.metrics.append(cycle_metrics)
        
        # Log results
        logger.info(f"Monitoring cycle completed - Health: {health.get('status', 'unknown')}, "
                   f"API Response: {api_perf.get('response_time', 0)}ms, "
                   f"Memory: {system.get('memory_mb', 0)}MB")
        
        return cycle_metrics
    
    def generate_report(self, cycles=10):
        """Generate a performance report"""
        if len(self.metrics) < cycles:
            logger.warning(f"Not enough metrics collected. Have {len(self.metrics)}, need {cycles}")
            return
        
        recent_metrics = self.metrics[-cycles:]
        
        # Calculate averages
        response_times = [m["api_performance"]["response_time"] 
                         for m in recent_metrics 
                         if m["api_performance"]["status"] == "success"]
        
        memory_usage = [m["system"]["memory_mb"] 
                       for m in recent_metrics 
                       if "memory_mb" in m["system"]]
        
        cpu_usage = [m["system"]["cpu_percent"] 
                    for m in recent_metrics 
                    if "cpu_percent" in m["system"]]
        
        # Health status summary
        health_statuses = [m["health"]["status"] for m in recent_metrics]
        healthy_count = health_statuses.count("healthy")
        health_percentage = (healthy_count / len(health_statuses)) * 100
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "cycles_analyzed": len(recent_metrics),
            "health_percentage": round(health_percentage, 2),
            "average_response_time_ms": round(sum(response_times) / len(response_times), 2) if response_times else 0,
            "average_memory_mb": round(sum(memory_usage) / len(memory_usage), 2) if memory_usage else 0,
            "average_cpu_percent": round(sum(cpu_usage) / len(cpu_usage), 2) if cpu_usage else 0,
            "min_response_time_ms": min(response_times) if response_times else 0,
            "max_response_time_ms": max(response_times) if response_times else 0,
            "min_memory_mb": min(memory_usage) if memory_usage else 0,
            "max_memory_mb": max(memory_usage) if memory_usage else 0
        }
        
        return report
    
    def save_metrics(self, filename="logs/performance_metrics.json"):
        """Save metrics to file"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(self.metrics, f, indent=2)
            logger.info(f"Metrics saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")

def main():
    """Main monitoring function"""
    monitor = PerformanceMonitor()
    
    print("Starting performance monitoring...")
    print("Press Ctrl+C to stop and generate report")
    
    try:
        cycle_count = 0
        while True:
            cycle_count += 1
            print(f"\nCycle {cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            metrics = monitor.run_monitoring_cycle()
            
            # Print summary
            health_status = metrics["health"].get("status", "unknown")
            response_time = metrics["api_performance"].get("response_time", 0)
            memory_mb = metrics["system"].get("memory_mb", 0)
            
            print(f"  Health: {health_status}")
            print(f"  API Response: {response_time}ms")
            print(f"  Memory: {memory_mb}MB")
            
            # Wait 30 seconds before next cycle
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n\nStopping monitoring...")
        
        # Generate and display report
        report = monitor.generate_report()
        if report:
            print("\n" + "="*50)
            print("PERFORMANCE REPORT")
            print("="*50)
            print(f"Cycles Analyzed: {report['cycles_analyzed']}")
            print(f"Health Percentage: {report['health_percentage']}%")
            print(f"Average Response Time: {report['average_response_time_ms']}ms")
            print(f"Response Time Range: {report['min_response_time_ms']}ms - {report['max_response_time_ms']}ms")
            print(f"Average Memory Usage: {report['average_memory_mb']}MB")
            print(f"Memory Range: {report['min_memory_mb']}MB - {report['max_memory_mb']}MB")
            print(f"Average CPU Usage: {report['average_cpu_percent']}%")
            print("="*50)
        
        # Save metrics
        monitor.save_metrics()

if __name__ == "__main__":
    main() 