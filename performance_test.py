#!/usr/bin/env python3
"""
Performance testing script for Mutual Fund Returns Tracker
"""

import asyncio
import aiohttp
import time
import statistics
from datetime import datetime
import json

# Configuration
BASE_URL = "http://127.0.0.1:5000"
TEST_ENDPOINTS = [
    "/",
    "/api/funds",
    "/health"
]
CONCURRENT_REQUESTS = 10
TOTAL_REQUESTS = 50

class PerformanceTester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.results = {}
        
    async def test_endpoint(self, session, endpoint, request_id):
        """Test a single endpoint and return timing data"""
        start_time = time.time()
        try:
            async with session.get(f"{self.base_url}{endpoint}") as response:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                return {
                    "endpoint": endpoint,
                    "request_id": request_id,
                    "status_code": response.status,
                    "response_time_ms": response_time,
                    "success": response.status == 200,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000
            
            return {
                "endpoint": endpoint,
                "request_id": request_id,
                "status_code": None,
                "response_time_ms": response_time,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_concurrent_tests(self, endpoint, num_requests, concurrent_limit):
        """Run concurrent tests for a specific endpoint"""
        connector = aiohttp.TCPConnector(limit=concurrent_limit)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            for i in range(num_requests):
                task = self.test_endpoint(session, endpoint, i + 1)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r for r in results if not isinstance(r, Exception)]
    
    def analyze_results(self, results):
        """Analyze test results and generate statistics"""
        if not results:
            return None
        
        response_times = [r["response_time_ms"] for r in results if r["success"]]
        success_count = sum(1 for r in results if r["success"])
        total_count = len(results)
        
        if not response_times:
            return {
                "endpoint": results[0]["endpoint"],
                "total_requests": total_count,
                "successful_requests": success_count,
                "success_rate": 0,
                "avg_response_time_ms": 0,
                "min_response_time_ms": 0,
                "max_response_time_ms": 0,
                "median_response_time_ms": 0,
                "std_deviation_ms": 0
            }
        
        return {
            "endpoint": results[0]["endpoint"],
            "total_requests": total_count,
            "successful_requests": success_count,
            "success_rate": (success_count / total_count) * 100,
            "avg_response_time_ms": statistics.mean(response_times),
            "min_response_time_ms": min(response_times),
            "max_response_time_ms": max(response_times),
            "median_response_time_ms": statistics.median(response_times),
            "std_deviation_ms": statistics.stdev(response_times) if len(response_times) > 1 else 0
        }
    
    async def run_full_test_suite(self):
        """Run complete performance test suite"""
        print(f"🚀 Starting Performance Test Suite")
        print(f"📍 Base URL: {self.base_url}")
        print(f"📊 Test Configuration: {TOTAL_REQUESTS} total requests, {CONCURRENT_REQUESTS} concurrent")
        print("=" * 60)
        
        all_results = {}
        
        for endpoint in TEST_ENDPOINTS:
            print(f"\n🔍 Testing endpoint: {endpoint}")
            print("-" * 40)
            
            # Run tests
            start_time = time.time()
            results = await self.run_concurrent_tests(endpoint, TOTAL_REQUESTS, CONCURRENT_REQUESTS)
            end_time = time.time()
            
            # Analyze results
            analysis = self.analyze_results(results)
            all_results[endpoint] = {
                "raw_results": results,
                "analysis": analysis,
                "test_duration": end_time - start_time
            }
            
            if analysis:
                print(f"✅ Success Rate: {analysis['success_rate']:.1f}%")
                print(f"⏱️  Average Response Time: {analysis['avg_response_time_ms']:.2f}ms")
                print(f"📈 Min/Max Response Time: {analysis['min_response_time_ms']:.2f}ms / {analysis['max_response_time_ms']:.2f}ms")
                print(f"📊 Median Response Time: {analysis['median_response_time_ms']:.2f}ms")
                print(f"📏 Standard Deviation: {analysis['std_deviation_ms']:.2f}ms")
                print(f"⏰ Test Duration: {analysis['test_duration']:.2f}s")
            else:
                print("❌ No successful requests")
        
        return all_results
    
    def generate_report(self, results):
        """Generate a comprehensive performance report"""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE TEST REPORT")
        print("=" * 60)
        
        # Overall summary
        total_requests = sum(r["analysis"]["total_requests"] for r in results.values() if r["analysis"])
        total_successful = sum(r["analysis"]["successful_requests"] for r in results.values() if r["analysis"])
        overall_success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
        
        print(f"\n📈 OVERALL SUMMARY:")
        print(f"   Total Requests: {total_requests}")
        print(f"   Successful Requests: {total_successful}")
        print(f"   Overall Success Rate: {overall_success_rate:.1f}%")
        
        # Endpoint comparison
        print(f"\n🔍 ENDPOINT COMPARISON:")
        print(f"{'Endpoint':<15} {'Success %':<10} {'Avg (ms)':<10} {'Min (ms)':<10} {'Max (ms)':<10}")
        print("-" * 65)
        
        for endpoint, data in results.items():
            if data["analysis"]:
                analysis = data["analysis"]
                print(f"{endpoint:<15} {analysis['success_rate']:<10.1f} {analysis['avg_response_time_ms']:<10.2f} "
                      f"{analysis['min_response_time_ms']:<10.2f} {analysis['max_response_time_ms']:<10.2f}")
        
        # Performance recommendations
        print(f"\n💡 PERFORMANCE RECOMMENDATIONS:")
        
        for endpoint, data in results.items():
            if data["analysis"]:
                analysis = data["analysis"]
                if analysis["avg_response_time_ms"] > 1000:
                    print(f"   ⚠️  {endpoint}: Consider caching (avg: {analysis['avg_response_time_ms']:.2f}ms)")
                elif analysis["avg_response_time_ms"] > 500:
                    print(f"   🔄 {endpoint}: Monitor performance (avg: {analysis['avg_response_time_ms']:.2f}ms)")
                else:
                    print(f"   ✅ {endpoint}: Good performance (avg: {analysis['avg_response_time_ms']:.2f}ms)")
        
        # Save detailed results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"performance_test_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                "test_config": {
                    "base_url": self.base_url,
                    "total_requests": TOTAL_REQUESTS,
                    "concurrent_requests": CONCURRENT_REQUESTS,
                    "timestamp": datetime.now().isoformat()
                },
                "results": results
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {filename}")

async def main():
    """Main function to run performance tests"""
    tester = PerformanceTester(BASE_URL)
    
    try:
        # Check if server is running
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/health", timeout=5) as response:
                    if response.status == 200:
                        print("✅ Server is running and healthy")
                    else:
                        print("⚠️  Server responded but health check failed")
                        return
            except Exception as e:
                print(f"❌ Cannot connect to server at {BASE_URL}")
                print(f"   Error: {e}")
                print(f"   Make sure the server is running with: python app.py")
                return
        
        # Run performance tests
        results = await tester.run_full_test_suite()
        tester.generate_report(results)
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 