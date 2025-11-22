# Splunk Log Ingestion Pipeline on AWS

Disclaimer: This project was built as part of a real-world security analytics environment at California State University, Fresno. The data used for manual log uploading was used from Fresno State's real AWS Production environment. All code, resources, and configurations shared here are educational templates and do not expose any proprietary or sensitive university data.

## Overview

This project demonstrates the design and deployment of a secure, scalable, and hybrid log ingestion pipeline that integrates **AWS services** with **Splunk Enterprise** for centralized monitoring and analysis. The solution supports both **automated log ingestion** from AWS services and **manual log uploads**, enabling flexibility for continuous and ad-hoc data analysis.

The pipeline leverages **Amazon CloudWatch**, **Kinesis Data Firehose**, **AWS Lambda**, **Amazon S3**, and **AWS Certificate Manager (ACM)** to route logs securely over HTTPS to a **Splunk HTTP Event Collector (HEC)** endpoint hosted on an EC2 instance behind an **Application Load Balancer (ALB)**.  
**Route 53** provides DNS resolution for a custom domain, ensuring secure HTTPS communication with TLS certificates managed by ACM.

Compared to a previous Architecture I had done for California State University, Fresno, this archtiecture cut down costs by ~70%

---

## Architecture Diagram

![image](https://github.com/user-attachments/assets/30fd17e4-d7c0-4206-8c0d-19c576b12166)


*Figure 1: Secure AWS-to-Splunk Log Ingestion Pipeline integrating Route 53, ACM, ALB, Firehose, and EC2.*

The architecture illustrates both automated and manual log ingestion paths:
- **Automated Ingestion**: CloudWatch subscriptions forward logs from various AWS Cloud Services directly to Firehose for delivery to Splunk.
- **Manual Uploads**: Administrators can manually upload log files into S3, which triggers a Lambda function that processes and forwards the logs to Firehose for ingestion into Splunk.

---

## Key Components

1. **AWS Cloud Services**
   - **Role:** Represents various AWS services generating logs such as WAF, VPC Flow Logs, and ALB Logs.
   - **Functionality:** These services continuously stream operational and security-related logs into CloudWatch for monitoring and downstream ingestion.

2. **Amazon CloudWatch**
   - **Role:** Acts as the central log aggregator for AWS resources.
   - **Functionality:** Creates **subscriptions** that automatically forward logs to Kinesis Data Firehose for ingestion into Splunk.
   - **Security:** IAM permissions limit access to approved log groups and delivery streams.

3. **AWS Lambda**
   - **Role:** Performs log transformation, preprocessing, and routing automation.
   - **Functionality:**
     - **Automated Path (optional):** Processes logs from CloudWatch before delivering them to Firehose.
     - **Manual Path:** Triggered by new S3 uploads to read and forward logs to Firehose for ingestion.
   - **Security:** Configured with least-privilege IAM roles granting access only to S3, Firehose, and CloudWatch.

4. **Amazon S3**
   - **Role:** Serves as long-term log storage and a source for manual log uploads.
   - **Functionality:** When new log files are uploaded, an event trigger invokes a Lambda function to process and forward logs to Firehose.
   - **Security:** Bucket policies enforce encryption at rest (SSE-S3) and controlled write access.

5. **Amazon Kinesis Data Firehose**
   - **Role:** Provides a fully managed data delivery service for streaming logs to Splunk.
   - **Functionality:** Buffers, transforms, and securely transmits log data over HTTPS to the ingestion endpoint (via ALB).
   - **Security:** Uses HTTPS for encrypted transport and IAM permissions for secure delivery.

6. **Application Load Balancer (ALB)**
   - **Role:** Acts as the secure entry point for log ingestion into Splunk.
   - **Functionality:** Listens on port 443 for HTTPS traffic, terminates SSL/TLS via ACM, and forwards requests to EC2 instances on port 8080.
   - **Security:** Configured with a dedicated security group that restricts inbound access to trusted IPs or AWS service integrations.

7. **Amazon EC2 (Splunk Enterprise)**
   - **Role:** Hosts Splunk Enterprise and the HTTP Event Collector (HEC) endpoint.
   - **Functionality:** Receives log data from Firehose through the ALB, indexes it, and populates dashboards for visualization and analytics.
   - **Security:** Deployed in public subnets within the VPC (with plans to move to private subnets); only accessible through the ALB and only has SSH access from university IP.

8. **AWS Route 53**
   - **Role:** Provides DNS resolution for a custom ingestion domain (e.g., `logs.example.com`).
   - **Functionality:** Routes HTTPS traffic to the ALB endpoint associated with Splunk.
   - **Security:** Works in tandem with ACM to ensure all data in transit is encrypted.

9. **AWS Certificate Manager (ACM)**
   - **Role:** Issues and manages SSL/TLS certificates for HTTPS communication.
   - **Functionality:** Enables encrypted HTTPS traffic on port 443 through the ALB.
   - **Security:** Automates certificate renewal and ensures end-to-end encryption.

---

## Log Ingestion Methods

1. **Automated Log Ingestion**
   - CloudWatch subscriptions automatically forward logs from various AWS Cloud Services
   - Logs are processed by Lambda and sent to Firehose.
   - Firehose securely delivers logs to the ALB endpoint, which forwards them to Splunk Enterprise for indexing and analysis.

2. **Manual Log Uploading**
   - Administrators can upload log files manually into the designated S3 bucket.
   - The upload event triggers a Lambda function that processes and forwards the logs into Firehose.
   - Firehose then transmits the data securely to Splunk via the ALB.
   - This method supports ad-hoc analysis, historical log ingestion, or forensic investigation.

---

## Traffic Flow

1. AWS services generate logs that are sent to CloudWatch.
2. CloudWatch subscriptions forward logs to Firehose.
3. Firehose streams the logs securely to the domain endpoint managed by Route 53.
4. Route 53 routes traffic to the ALB (port 443).
5. The ALB terminates HTTPS and forwards requests to EC2 (port 8080).
6. Splunk’s HTTP Event Collector (HEC) ingests the data for indexing and visualization.
7. For manual uploads, S3 triggers Lambda → Firehose → Splunk ingestion.

---

## Objectives

- **Secure Log Ingestion:** Deliver logs via HTTPS using ACM-managed TLS certificates.
- **Custom Domain Integration:** Use Route 53 to manage DNS for log ingestion endpoints.
- **Automation and Flexibility:** Support continuous ingestion (CloudWatch) and manual uploads (S3).
- **Centralized Analytics:** Enable Splunk dashboards for real-time monitoring of AWS WAF, VPC Flow, and ALB logs.
- **Scalability and Efficiency:** Utilize AWS managed services (Lambda, Firehose, ALB) for a serverless, auto-scaling design.

---

## Security Considerations

- **Network Isolation (Working on Implementing):** ALB and EC2 are currently deployed in public subnets within a VPC. However, the goal is to soon restrict public access by putting the ALB and EC2 in private subnets.
- **Access Control:** Security groups limit inbound traffic to approved IP ranges or AWS service sources.
- **Encryption:** TLS (HTTPS) for all data in transit; S3 encryption for data at rest.
- **Least Privilege IAM:** Lambda, Firehose, and CloudWatch roles follow least-privilege principles.
- **Monitoring:** CloudTrail and VPC Flow Logs track API activity and network traffic for auditing.

---

## Conclusion

This project demonstrates the implementation of a **hybrid AWS-to-Splunk SIEM pipeline** that securely ingests, processes, and visualizes log data from multiple AWS sources.  
By integrating **Route 53**, **ACM**, **ALB**, **Lambda**, **S3**, **Firehose**, and **CloudWatch**, the architecture provides both **automated log streaming** and **manual ingestion workflows** for comprehensive security monitoring.

The solution is scalable, cost-efficient, and reflects production-grade SIEM design principles, ensuring data confidentiality, integrity, and availability across the ingestion pipeline.

![image](https://github.com/user-attachments/assets/d79c11fe-051f-49ff-9d5f-4d95965261cf)
![image](https://github.com/user-attachments/assets/ebbea550-21d1-4434-b2b8-230784565959)
![image](https://github.com/user-attachments/assets/2742912d-fd27-424b-a317-69dfdea07215)
