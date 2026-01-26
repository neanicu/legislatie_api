#!/usr/bin/env python3
"""
Monitoring endpoint for Legislatie API Client.
Exposes health metrics and performance statistics.
"""

import json
import time
import threading
from datetime import datetime
from typing import Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from legislatie_client import LegislatieClient


class MetricsCollector:
    """Collects and stores system metrics."""

    def __init__(self):
        self.metrics = {
            "health_checks": [],
            "search_requests": [],
            "cache_stats": [],
            "errors": [],
            "start_time": time.time(),
        }
        self.lock = threading.Lock()

    def record_health_check(self, health_data: Dict[str, Any]):
        """Record a health check result."""
        with self.lock:
            self.metrics["health_checks"].append(
                {"timestamp": datetime.now().isoformat(), "data": health_data}
            )
            # Keep only last 100 checks
            if len(self.metrics["health_checks"]) > 100:
                self.metrics["health_checks"] = self.metrics["health_checks"][-100:]

    def record_search_request(
        self, params: Dict[str, Any], duration: float, success: bool
    ):
        """Record a search request."""
        with self.lock:
            self.metrics["search_requests"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "params": params,
                    "duration": duration,
                    "success": success,
                }
            )
            # Keep only last 1000 requests
            if len(self.metrics["search_requests"]) > 1000:
                self.metrics["search_requests"] = self.metrics["search_requests"][
                    -1000:
                ]

    def record_cache_stats(self, stats: Dict[str, Any]):
        """Record cache statistics."""
        with self.lock:
            self.metrics["cache_stats"].append(
                {"timestamp": datetime.now().isoformat(), "stats": stats}
            )
            # Keep only last 100 stats
            if len(self.metrics["cache_stats"]) > 100:
                self.metrics["cache_stats"] = self.metrics["cache_stats"][-100:]

    def record_error(self, error_type: str, message: str, details: Any = None):
        """Record an error."""
        with self.lock:
            self.metrics["errors"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "type": error_type,
                    "message": message,
                    "details": details,
                }
            )
            # Keep only last 100 errors
            if len(self.metrics["errors"]) > 100:
                self.metrics["errors"] = self.metrics["errors"][-100:]

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Calculate summary metrics from collected data."""
        with self.lock:
            now = time.time()
            uptime = now - self.metrics["start_time"]

            # Calculate health check success rate
            health_checks = self.metrics["health_checks"]
            if health_checks:
                last_health = health_checks[-1]["data"]
                overall_health = last_health.get("overall", "unknown")
            else:
                overall_health = "unknown"

            # Calculate search request statistics
            search_requests = self.metrics["search_requests"]
            if search_requests:
                successful_searches = sum(1 for r in search_requests if r["success"])
                total_searches = len(search_requests)
                success_rate = (
                    successful_searches / total_searches if total_searches > 0 else 0
                )

                # Average duration of successful searches
                successful_durations = [
                    r["duration"] for r in search_requests if r["success"]
                ]
                avg_duration = (
                    sum(successful_durations) / len(successful_durations)
                    if successful_durations
                    else 0
                )
            else:
                success_rate = 0
                avg_duration = 0
                total_searches = 0

            # Get latest cache stats
            cache_stats = self.metrics["cache_stats"]
            latest_cache = cache_stats[-1]["stats"] if cache_stats else {}

            # Error count in last hour
            one_hour_ago = datetime.fromtimestamp(now - 3600).isoformat()
            recent_errors = [
                e for e in self.metrics["errors"] if e["timestamp"] > one_hour_ago
            ]

            return {
                "uptime_seconds": uptime,
                "overall_health": overall_health,
                "search_requests_total": total_searches,
                "search_success_rate": success_rate,
                "search_avg_duration_seconds": avg_duration,
                "cache_size": latest_cache.get("size", 0),
                "cache_type": latest_cache.get("type", "unknown"),
                "errors_last_hour": len(recent_errors),
                "timestamp": datetime.now().isoformat(),
            }

    def get_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        summary = self.get_summary_metrics()

        metrics = []

        # Uptime
        metrics.append(f'legislatie_uptime_seconds {summary["uptime_seconds"]}')

        # Health status (1 = healthy, 0 = unhealthy, -1 = unknown)
        health_map = {"healthy": 1, "unhealthy": 0, "unknown": -1}
        metrics.append(
            f'legislatie_health_status {health_map.get(summary["overall_health"], -1)}'
        )

        # Search requests
        metrics.append(
            f'legislatie_search_requests_total {summary["search_requests_total"]}'
        )
        metrics.append(
            f'legislatie_search_success_rate {summary["search_success_rate"]}'
        )
        metrics.append(
            f'legislatie_search_avg_duration_seconds {summary["search_avg_duration_seconds"]}'
        )

        # Cache
        metrics.append(f'legislatie_cache_size {summary["cache_size"]}')
        cache_type_map = {"memory": 0, "diskcache": 1, "unknown": 2}
        metrics.append(
            f'legislatie_cache_type {cache_type_map.get(summary["cache_type"], 2)}'
        )

        # Errors
        metrics.append(f'legislatie_errors_last_hour {summary["errors_last_hour"]}')

        return "\n".join(metrics)


# Global metrics collector
collector = MetricsCollector()


class MonitoringHandler(BaseHTTPRequestHandler):
    """HTTP handler for monitoring endpoints."""

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        elif self.path == "/metrics":
            self._handle_metrics()
        elif self.path == "/metrics/prometheus":
            self._handle_prometheus_metrics()
        elif self.path == "/stats":
            self._handle_stats()
        else:
            self.send_error(404, "Endpoint not found")

    def _handle_health(self):
        """Return detailed health check."""
        try:
            client = LegislatieClient()
            health = client.check_health()
            collector.record_health_check(health)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2, default=str).encode("utf-8"))
        except Exception as e:
            collector.record_error("health_check_failed", str(e))
            self.send_error(500, f"Health check failed: {e}")

    def _handle_metrics(self):
        """Return JSON metrics."""
        try:
            metrics = collector.get_summary_metrics()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(metrics, indent=2).encode("utf-8"))
        except Exception as e:
            collector.record_error("metrics_failed", str(e))
            self.send_error(500, f"Metrics collection failed: {e}")

    def _handle_prometheus_metrics(self):
        """Return Prometheus format metrics."""
        try:
            metrics = collector.get_prometheus_metrics()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(metrics.encode("utf-8"))
        except Exception as e:
            collector.record_error("prometheus_metrics_failed", str(e))
            self.send_error(500, f"Prometheus metrics failed: {e}")

    def _handle_stats(self):
        """Return detailed statistics."""
        try:
            with collector.lock:
                stats = {
                    "summary": collector.get_summary_metrics(),
                    "recent_health_checks": collector.metrics["health_checks"][-10:],
                    "recent_search_requests": collector.metrics["search_requests"][
                        -20:
                    ],
                    "recent_cache_stats": collector.metrics["cache_stats"][-10:],
                    "recent_errors": collector.metrics["errors"][-20:],
                    "total_health_checks": len(collector.metrics["health_checks"]),
                    "total_search_requests": len(collector.metrics["search_requests"]),
                    "total_errors": len(collector.metrics["errors"]),
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(stats, indent=2, default=str).encode("utf-8"))
        except Exception as e:
            collector.record_error("stats_failed", str(e))
            self.send_error(500, f"Stats collection failed: {e}")

    def log_message(self, format, *args):
        """Override to suppress default logging."""
        # Only log errors
        if args[1] != "200":
            super().log_message(format, *args)


def start_monitoring_server(host="0.0.0.0", port=9090):
    """Start the monitoring HTTP server."""
    server = HTTPServer((host, port), MonitoringHandler)
    print(f"Monitoring server started on http://{host}:{port}")
    print("Available endpoints:")
    print(f"  http://{host}:{port}/health       - Detailed health check")
    print(f"  http://{host}:{port}/metrics      - JSON metrics summary")
    print(f"  http://{host}:{port}/metrics/prometheus - Prometheus metrics")
    print(f"  http://{host}:{port}/stats        - Detailed statistics")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down monitoring server...")
        server.server_close()


def instrument_client(client: LegislatieClient) -> LegislatieClient:
    """Instrument a LegislatieClient to record metrics."""
    original_search = client.search

    def instrumented_search(*args, **kwargs):
        start_time = time.time()
        try:
            results = original_search(*args, **kwargs)
            duration = time.time() - start_time
            collector.record_search_request(kwargs, duration, True)
            return results
        except Exception as e:
            duration = time.time() - start_time
            collector.record_search_request(kwargs, duration, False)
            collector.record_error("search_failed", str(e), kwargs)
            raise

    client.search = instrumented_search
    return client


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Legislatie API Monitoring Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9090, help="Port to listen on")
    parser.add_argument(
        "--health-check-interval",
        type=int,
        default=300,
        help="Health check interval in seconds (0 to disable)",
    )

    args = parser.parse_args()

    # Start background health checking if interval > 0
    if args.health_check_interval > 0:

        def health_check_loop():
            while True:
                try:
                    client = LegislatieClient()
                    health = client.check_health()
                    collector.record_health_check(health)

                    # Record cache stats
                    stats = client.cache.get_stats()
                    collector.record_cache_stats(stats)
                except Exception as e:
                    collector.record_error("background_health_check_failed", str(e))

                time.sleep(args.health_check_interval)

        thread = threading.Thread(target=health_check_loop, daemon=True)
        thread.start()
        print(
            f"Background health checking enabled (interval: {args.health_check_interval}s)"
        )

    start_monitoring_server(args.host, args.port)
