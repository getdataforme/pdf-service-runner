#!/usr/bin/env python3
"""
Test script for the PDF Extraction Service
"""
import requests
import json
import time
import sys

def test_service():
    base_url = "http://localhost:8000"
    
    print("🧪 Testing PDF Extraction Service")
    print("=" * 50)
    
    # Test health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("✅ Health check passed")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to service. Is it running on localhost:8000?")
        return
    
    # Test PDF extraction
    print("\n2. Testing PDF extraction...")
    test_request = {
        "county_name": "orangecounty",
        "document_type": "complaint",
        "date_to": "2025-01-01"
    }
    
    try:
        response = requests.post(
            f"{base_url}/extract",
            headers={"Content-Type": "application/json"},
            json=test_request
        )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result["job_id"]
            print(f"✅ Extraction job started: {job_id}")
            
            # Poll for status
            print("\n3. Monitoring job status...")
            max_polls = 30  # Maximum 5 minutes (30 * 10 seconds)
            poll_count = 0
            
            while poll_count < max_polls:
                status_response = requests.get(f"{base_url}/status/{job_id}")
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data["status"]
                    message = status_data["message"]
                    
                    print(f"📊 Status: {status} - {message}")
                    
                    if status == "completed":
                        print("✅ Job completed successfully!")
                        if "result" in status_data:
                            result = status_data["result"]
                            print(f"📄 Total files: {result.get('total_files', 'N/A')}")
                            print(f"✅ Successful extractions: {result.get('successful_extractions', 'N/A')}")
                            print(f"❌ Failed extractions: {result.get('failed_extractions', 'N/A')}")
                        break
                    elif status == "failed":
                        print(f"❌ Job failed: {status_data.get('error', 'Unknown error')}")
                        break
                    else:
                        time.sleep(10)  # Wait 10 seconds before next poll
                        poll_count += 1
                else:
                    print(f"❌ Error checking status: {status_response.status_code}")
                    break
            
            if poll_count >= max_polls:
                print("⏰ Job is taking longer than expected. Check the logs.")
                
        else:
            print(f"❌ Failed to start extraction: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error during extraction test: {str(e)}")
    
    # Test job listing
    print("\n4. Testing job listing...")
    try:
        response = requests.get(f"{base_url}/jobs")
        if response.status_code == 200:
            jobs = response.json()
            print(f"✅ Jobs endpoint accessible. Found {len(jobs.get('jobs', {}))} jobs.")
        else:
            print(f"❌ Jobs endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing jobs endpoint: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Test complete!")

if __name__ == "__main__":
    test_service()
