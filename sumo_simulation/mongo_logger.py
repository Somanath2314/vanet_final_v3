"""
mongo_logger.py

Simple MongoDB logger for VANET simulation outputs.

Environment variables (optional):
 - MONGO_URI: MongoDB connection string (default: mongodb://localhost:27017)
 - MONGO_DB:   Database name (default: vanet)

Usage:
  from mongo_logger import MongoMetricsLogger
  logger = MongoMetricsLogger.from_env()
  if logger:
      logger.insert_packets(packets_df)
      logger.insert_metrics(metrics_dict)

This module handles missing pymongo gracefully (it will return None from from_env
if pymongo is not installed or connection cannot be established).
"""

from typing import Optional, Dict, Any
import os
import time
import traceback

try:
    from pymongo import MongoClient
except Exception:
    MongoClient = None

import pandas as pd


class MongoMetricsLogger:
    def __init__(self, client, db_name: str = "vanet"):
        self.client = client
        self.db = client[db_name]
        self.packets_col = self.db.get_collection("packets")
        self.metrics_col = self.db.get_collection("metrics")
        self.tripinfo_col = self.db.get_collection("tripinfo")
        self.summary_col = self.db.get_collection("summary")

    @staticmethod
    def from_env() -> Optional['MongoMetricsLogger']:
        """Create a logger using env vars. Returns None if pymongo not available or connection fails."""
        if MongoClient is None:
            print("[mongo_logger] pymongo not installed - skipping MongoDB logging")
            return None

        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.environ.get("MONGO_DB", "vanet")
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            # quick check
            client.server_info()
            return MongoMetricsLogger(client, db_name)
        except Exception:
            print("[mongo_logger] Could not connect to MongoDB at", uri)
            # print traceback for developer visibility
            traceback.print_exc()
            return None

    def _records_from_df(self, df: pd.DataFrame):
        if df is None or df.empty:
            return []
        # Replace NaN with None for MongoDB
        clean = df.where(pd.notnull(df), None)
        # Convert numpy types to native Python types via to_dict
        recs = clean.to_dict(orient="records")
        # add ingestion timestamp
        ts = time.time()
        for r in recs:
            r["ingest_ts"] = ts
        return recs

    def insert_packets(self, df: pd.DataFrame):
        try:
            recs = self._records_from_df(df)
            if recs:
                self.packets_col.insert_many(recs)
                print(f"[mongo_logger] Inserted {len(recs)} packet records to MongoDB")
        except Exception:
            print("[mongo_logger] Error inserting packet records to MongoDB")
            traceback.print_exc()

    def insert_metrics(self, metrics: Dict[str, Any]):
        try:
            if not metrics:
                return
            m = dict(metrics)
            m["ingest_ts"] = time.time()
            self.metrics_col.insert_one(m)
            print("[mongo_logger] Inserted metrics document to MongoDB")
        except Exception:
            print("[mongo_logger] Error inserting metrics to MongoDB")
            traceback.print_exc()

    def insert_tripinfo(self, df: pd.DataFrame):
        try:
            recs = self._records_from_df(df)
            if recs:
                self.tripinfo_col.insert_many(recs)
                print(f"[mongo_logger] Inserted {len(recs)} tripinfo records to MongoDB")
        except Exception:
            print("[mongo_logger] Error inserting tripinfo to MongoDB")
            traceback.print_exc()

    def insert_summary(self, df: pd.DataFrame):
        try:
            recs = self._records_from_df(df)
            if recs:
                self.summary_col.insert_many(recs)
                print(f"[mongo_logger] Inserted {len(recs)} summary step records to MongoDB")
        except Exception:
            print("[mongo_logger] Error inserting summary to MongoDB")
            traceback.print_exc()
