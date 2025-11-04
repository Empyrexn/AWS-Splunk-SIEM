## Splunk Setup and Reproducibility Guide

This section provides a step-by-step walkthrough for configuring Splunk and AWS services to reproduce the AWS-to-Splunk ingestion pipeline shown in this repository.  
It includes setup for the Splunk HTTP Event Collector (HEC), configuration of Firehose delivery, creation of a custom `aws:waf` sourcetype, and installation of the Splunk Add-on for AWS to handle built-in sourcetypes like ALB and VPC Flow Logs.

---

### 1. Create a Splunk HTTP Event Collector (HEC) Token for Firehose

**In Splunk Web (on your EC2 instance):**
1. Navigate to **Settings → Data Inputs → HTTP Event Collector (HEC)**.  
2. Click **Global Settings**:
   - **Enable SSL:** On  
   - **HTTP Port Number:** `8088` (default) or your configured port  
   - Save  
3. Click **New Token**:
   - **Name:** `firehose-hec`  
   - **Source type:** Leave Manual (Firehose will override per stream)  
   - **Index:** Select your target index (e.g., `main` or `security`)  
   - **Enable indexer acknowledgment:** On  
   - Save and **copy the token value**  

**Optional:** Test HEC health.
```bash
curl -k https://<your-domain-or-alb>/services/collector/health
# Expect: {"text":"HEC is healthy","code":17}
````

---

### 2. Configure Amazon Kinesis Data Firehose → Splunk

1. **Create or edit** your Firehose delivery stream.
2. **Source:** CloudWatch Logs, Direct PUT, or S3.
3. **Destination:** Splunk.
4. **HTTP Endpoint (HEC) URL:**

   ```
   https://<your Route53 domain or ALB DNS>:443/services/collector
   ```

   * Use port **443** if TLS terminates at the ALB with ACM.
5. **HEC Token:** Paste the token created in Step 1.
6. **Retry Options:** Increase delivery duration if needed.
7. **S3 Backup:** Enable for “All Events” or “Failed Events.”
8. **Index Acknowledgment:** Must match HEC configuration (enabled).
9. **Sourcetype Override:** (Optional per stream)

   * WAF Logs → `aws:waf`
   * ALB Logs → `aws:elb:accesslogs`
   * VPC Flow Logs → `aws:cloudwatchlogs:vpcflow`
10. Save and start Firehose delivery.

---

### 3. Create a Custom `aws:waf` Sourcetype

You can define this in **Splunk Web** or directly in configuration files.

#### A. Create via Splunk Web

1. Go to **Settings → Source Types → New Source Type**.
2. **Name:** `aws:waf`
3. **Category:** Security
4. **Advanced Settings:**

   ```
   SHOULD_LINEMERGE = false
   TRUNCATE = 50000
   TIME_PREFIX = "timestamp":\s*
   TIME_FORMAT = %s%3N
   INDEXED_EXTRACTIONS = json
   ```
5. Save the sourcetype.

#### B. Create via Configuration Files

Add to `$SPLUNK_HOME/etc/system/local/props.conf` or an app’s local folder:

```ini
[aws:waf:json]
SHOULD_LINEMERGE = false
TIME_FORMAT = %s%Q
TIME_PREFIX = "timestamp":
KV_MODE = json
```

Restart Splunk after saving.

---

### 4. Install the Splunk Add-on for AWS

The Splunk Add-on for AWS provides field extractions and data models for common AWS sourcetypes.

**Steps:**

1. Go to **Manage Apps → Browse more apps**.
2. Search for **“Splunk Add-on for Amazon Web Services”** and install it.
3. Restart Splunk when prompted.

**Common Sourcetypes Provided by the Add-on:**

| Log Type              | Sourcetype                   |
| --------------------- | ---------------------------- |
| ALB / ELB Access Logs | `aws:elb:accesslogs`         |
| VPC Flow Logs         | `aws:cloudwatchlogs:vpcflow` |
| CloudTrail Logs       | `aws:cloudtrail`             |
| GuardDuty Findings    | `aws:guardduty:findings`     |

These sourcetypes automatically enable field extractions and CIM compliance.

---

### 5. Map Firehose Streams to Correct Sourcetypes

| Source          | Firehose Destination Sourcetype |
| --------------- | ------------------------------- |
| AWS WAF Logs    | `aws:waf`                       |
| ALB Access Logs | `aws:elb:accesslogs`            |
| VPC Flow Logs   | `aws:cloudwatchlogs:vpcflow`    |

Set these in the **Firehose destination configuration** or via the **Splunk HEC token defaults**.

---

### 6. Route 53 / ALB / ACM Configuration Checklist

* **Route 53:** `logs.example.edu` → ALB (Alias Record)
* **ACM Certificate:** Issue in the same region as ALB, attach to the **443 listener**.
* **ALB Listener:** Port 443 (HTTPS) → Target Group (EC2 on port 8088 or 8080)
* **Security Groups:**

  * ALB SG: Allow inbound 443 from trusted sources or AWS service ranges
  * EC2 SG: Allow inbound HEC port (8088/8080) only from the ALB SG
* **Health Check Path:** `/services/collector/health`

---

### 7. Validate End-to-End Connectivity

**Check HEC health:**

```bash
curl -k https://logs.example.edu/services/collector/health
```

**Send a test event:**

```bash
curl -k https://logs.example.edu/services/collector \
  -H "Authorization: Splunk <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"sourcetype":"aws:waf","event":{"test":"ok","timestamp":1720000000000}}'
```

**Verify ingestion in Splunk:**

```spl
index=<your_index> sourcetype=aws:waf test=ok
```

**Check Firehose Metrics:**

* Navigate to **Kinesis → Delivery Streams → Monitoring**
* Confirm successful deliveries and retry count = 0
* Review S3 backup for failed events if any

---

### 8. Troubleshooting Tips

| Issue                   | Likely Cause                                | Resolution                                                     |
| ----------------------- | ------------------------------------------- | -------------------------------------------------------------- |
| Firehose delivery fails | HEC acknowledgment disabled or timeout      | Ensure `indexer acknowledgment` is enabled on HEC and Firehose |
| No events in Splunk     | Wrong HEC URL or port                       | Verify ALB listener and target port mapping                    |
| Timestamps incorrect    | Missing or wrong `TIME_FORMAT` in `aws:waf` | Ensure `%s%3N` for epoch milliseconds                          |
| No field extractions    | Incorrect sourcetype                        | Match sourcetype with Splunk Add-on for AWS                    |
| TLS handshake errors    | Invalid ACM certificate or ALB listener     | Revalidate ACM and listener configuration                      |


