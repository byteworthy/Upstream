# Vendor Security Questionnaire Responses

**Upstream Healthcare Platform - Security Assessment Answers**

Version 1.0 | February 2026

---

## Table of Contents

1. [Company Information](#company-information)
2. [Data Handling and Privacy](#data-handling-and-privacy)
3. [Infrastructure Security](#infrastructure-security)
4. [Application Security](#application-security)
5. [Access Control and Authentication](#access-control-and-authentication)
6. [Business Continuity and Disaster Recovery](#business-continuity-and-disaster-recovery)
7. [Incident Response](#incident-response)
8. [Compliance and Certifications](#compliance-and-certifications)
9. [Third-Party and Sub-processor Management](#third-party-and-sub-processor-management)
10. [Security Governance](#security-governance)

---

## Company Information

### Q1.1: What is the legal name and address of your organization?

**Answer**: Upstream Healthcare Platform, Inc.

*Address available upon request through official procurement channels.*

### Q1.2: How long has your organization been in business?

**Answer**: Upstream Healthcare Platform was founded to provide AI-powered healthcare technology solutions. Specific founding date and operational history available upon request.

### Q1.3: What is the primary business function of your organization?

**Answer**: Upstream Healthcare Platform provides AI-powered clinical decision support, patient risk stratification, and healthcare analytics services to healthcare organizations including hospitals, health systems, and clinics.

### Q1.4: Do you have a dedicated security team?

**Answer**: Yes. We maintain a dedicated security team responsible for:
- Security architecture and engineering
- Security operations and monitoring
- Vulnerability management
- Incident response
- Compliance and audit support

---

## Data Handling and Privacy

### Q2.1: What types of data will you process on our behalf?

**Answer**: Upstream Healthcare Platform may process the following data types:
- Protected Health Information (PHI) as defined by HIPAA
- Electronic Protected Health Information (ePHI)
- Patient demographic information
- Clinical data (diagnoses, procedures, medications, lab results)
- Provider information
- Administrative and billing data

### Q2.2: Where is customer data stored geographically?

**Answer**: All customer data is stored within the United States. We do not transfer PHI outside of the United States without explicit written customer consent.

**Data Center Locations**:
- Primary: US-based cloud infrastructure (specific region configurable per customer requirements)
- Disaster Recovery: Geographically separate US-based region

### Q2.3: How is data segregated between customers?

**Answer**: Customer data is logically segregated using:
- **Tenant Isolation**: Each customer operates within a dedicated logical tenant with unique identifiers
- **Database Separation**: Customer data is segregated at the database level using tenant-specific schemas or dedicated databases
- **Network Isolation**: Customers are isolated at the network layer using Virtual Private Clouds (VPCs) and security groups
- **Encryption Key Separation**: Each customer's data is encrypted with customer-specific encryption keys

### Q2.4: How is data encrypted at rest?

**Answer**:
- **Encryption Standard**: AES-256 encryption
- **Key Management**: Keys managed through cloud provider Key Management Service (KMS) with hardware security module (HSM) backing
- **Coverage**: All databases, file storage, backups, and logs containing PHI are encrypted at rest
- **Key Rotation**: Encryption keys are rotated annually or upon request

### Q2.5: How is data encrypted in transit?

**Answer**:
- **Protocol**: TLS 1.3 (minimum TLS 1.2 supported for legacy systems)
- **Certificate Management**: Certificates managed through automated certificate management with 90-day rotation
- **Internal Communication**: All internal service-to-service communication is encrypted
- **API Security**: All API endpoints require HTTPS; HTTP connections are rejected

### Q2.6: What is your data retention policy?

**Answer**:
- **Active Data**: Retained for the duration of the service agreement
- **Backup Retention**: 90 days for operational backups
- **Post-Termination**: Data returned or destroyed within 30 days of contract termination (as specified in BAA)
- **Audit Logs**: Retained for 7 years to support compliance requirements

### Q2.7: How is data disposed of at end of contract?

**Answer**:
- **Return Option**: Data can be exported in standard formats (JSON, CSV, HL7 FHIR)
- **Destruction Method**: Data destruction follows NIST SP 800-88 guidelines for media sanitization
- **Certification**: Written certification of destruction provided within 30 days of destruction
- **Backup Destruction**: All backup copies destroyed according to the same standards

### Q2.8: Do you use customer data for any purposes other than providing the service?

**Answer**: No. Customer data is used solely for providing contracted services. We do NOT use customer data for:
- Training machine learning models without explicit written authorization
- Marketing or advertising
- Sale to third parties
- Any purpose not explicitly authorized in the service agreement

### Q2.9: Do you de-identify or anonymize data?

**Answer**: Yes, when authorized by the customer:
- De-identification follows HIPAA Safe Harbor or Expert Determination methods (45 CFR 164.514)
- De-identified data may be used for service improvement only with customer consent
- Customers retain control over de-identification decisions

---

## Infrastructure Security

### Q3.1: Where is your infrastructure hosted?

**Answer**: Upstream Healthcare Platform is hosted on enterprise-grade cloud infrastructure:
- **Primary Provider**: Major cloud provider with SOC 2 Type II, ISO 27001, and HIPAA compliance
- **Architecture**: Multi-availability zone deployment for high availability
- **Region**: US-based regions with customer-configurable region selection

### Q3.2: What physical security controls are in place at data centers?

**Answer**: Our cloud infrastructure providers maintain:
- 24/7/365 security personnel and surveillance
- Biometric access controls
- Man-trap entry systems
- Perimeter security (fencing, barriers)
- Environmental controls (fire suppression, climate control, flood prevention)
- Regular third-party audits (SOC 2 Type II)

### Q3.3: How is network security implemented?

**Answer**:
- **Firewall Protection**: Web Application Firewall (WAF) and network firewalls
- **DDoS Protection**: Cloud-native DDoS mitigation services
- **Network Segmentation**: VPC isolation with security groups and network ACLs
- **Intrusion Detection**: Network-based and host-based intrusion detection systems (IDS/IPS)
- **Traffic Monitoring**: Real-time traffic analysis and anomaly detection

### Q3.4: How are servers and systems hardened?

**Answer**:
- **Baseline Configuration**: CIS Benchmarks applied to all systems
- **Minimal Installation**: Only required services and packages installed
- **Patch Management**: Security patches applied within 30 days (critical patches within 72 hours)
- **Configuration Management**: Infrastructure as Code (IaC) ensuring consistent, auditable configurations
- **Regular Scanning**: Weekly vulnerability scans with remediation tracking

### Q3.5: How are containers and orchestration secured?

**Answer**:
- **Container Scanning**: Images scanned for vulnerabilities before deployment
- **Base Images**: Minimal, hardened base images from trusted registries
- **Runtime Security**: Container runtime monitoring and anomaly detection
- **Secrets Management**: Secrets injected at runtime, never baked into images
- **Network Policies**: Kubernetes network policies restricting pod-to-pod communication

### Q3.6: How do you manage vulnerabilities?

**Answer**:
- **Scanning Frequency**: Weekly automated scans (infrastructure and application)
- **Penetration Testing**: Annual third-party penetration tests
- **Remediation SLAs**:
  - Critical: 72 hours
  - High: 7 days
  - Medium: 30 days
  - Low: 90 days
- **Tracking**: All vulnerabilities tracked in a centralized system with ownership and deadlines

---

## Application Security

### Q4.1: What secure development practices do you follow?

**Answer**:
- **Secure SDLC**: Security integrated throughout the development lifecycle
- **Code Review**: All code changes require peer review before merge
- **Static Analysis**: SAST tools run on every code commit
- **Dynamic Analysis**: DAST testing performed in staging environments
- **Dependency Scanning**: Third-party libraries scanned for known vulnerabilities
- **Security Training**: Annual secure coding training for all developers

### Q4.2: How do you protect against OWASP Top 10 vulnerabilities?

**Answer**:

| Vulnerability | Mitigation |
|---------------|------------|
| Injection | Parameterized queries, ORM usage, input validation |
| Broken Authentication | MFA, secure session management, password policies |
| Sensitive Data Exposure | Encryption at rest/transit, data masking, access controls |
| XML External Entities | XML parsing disabled or configured securely |
| Broken Access Control | RBAC, attribute-based access control, authorization checks |
| Security Misconfiguration | Automated configuration management, hardened defaults |
| Cross-Site Scripting | Output encoding, Content Security Policy, input validation |
| Insecure Deserialization | Type checking, integrity verification, limited deserialization |
| Using Components with Known Vulnerabilities | Dependency scanning, automated updates |
| Insufficient Logging & Monitoring | Comprehensive audit logging, SIEM integration |

### Q4.3: How is API security implemented?

**Answer**:
- **Authentication**: OAuth 2.0 / OpenID Connect with JWT tokens
- **Authorization**: Role-based and attribute-based access control
- **Rate Limiting**: Per-endpoint and per-user rate limits
- **Input Validation**: Schema validation on all API inputs
- **Output Filtering**: Response filtering to prevent data leakage
- **API Gateway**: Centralized API gateway for security policy enforcement

### Q4.4: How do you manage secrets and credentials?

**Answer**:
- **Secrets Management**: Centralized secrets management service (e.g., HashiCorp Vault or cloud-native)
- **No Hardcoded Secrets**: Secrets never stored in code or configuration files
- **Rotation**: Secrets rotated regularly (API keys quarterly, service accounts annually)
- **Access Logging**: All secret access is logged and auditable

---

## Access Control and Authentication

### Q5.1: How do users authenticate to your system?

**Answer**:
- **Primary Authentication**: Username/password with strong password requirements
- **Multi-Factor Authentication**: MFA required for all user accounts
- **Single Sign-On**: SAML 2.0 and OIDC integration supported
- **Session Management**: Secure session tokens with configurable timeout

### Q5.2: What are your password requirements?

**Answer**:
- Minimum 12 characters
- Complexity requirements (uppercase, lowercase, numbers, special characters)
- Password history (last 12 passwords cannot be reused)
- Account lockout after 5 failed attempts
- Password expiration: 90 days (configurable per customer policy)

### Q5.3: How is access control implemented?

**Answer**:
- **Model**: Role-Based Access Control (RBAC)
- **Principle of Least Privilege**: Users granted minimum access required for their role
- **Access Reviews**: Quarterly access reviews for all user accounts
- **Privileged Access**: Administrative access requires additional approval and MFA
- **Just-in-Time Access**: Temporary elevated access with automatic expiration

### Q5.4: How do you manage administrative/privileged access?

**Answer**:
- Privileged accounts are separate from regular user accounts
- All privileged access requires MFA
- Administrative actions are logged with enhanced detail
- Emergency access ("break glass") procedures documented and audited
- Quarterly review of privileged access

### Q5.5: How do you handle employee offboarding?

**Answer**:
- Access revoked within 24 hours of termination notification
- Immediate revocation for involuntary terminations
- Automated deprovisioning integrated with HR systems
- Verification of access removal documented

---

## Business Continuity and Disaster Recovery

### Q6.1: What is your Recovery Time Objective (RTO)?

**Answer**: 4 hours for critical systems. Full service restoration within 24 hours.

### Q6.2: What is your Recovery Point Objective (RPO)?

**Answer**: 1 hour. Transaction log backups performed every 15 minutes.

### Q6.3: How often do you test your disaster recovery plan?

**Answer**:
- **Tabletop Exercises**: Quarterly
- **Partial Failover Tests**: Semi-annually
- **Full DR Failover**: Annually
- **Backup Restoration Tests**: Monthly

### Q6.4: What is your backup strategy?

**Answer**:
- **Database Backups**: Continuous replication with point-in-time recovery
- **File Storage**: Daily incremental, weekly full backups
- **Backup Location**: Geographically separate region from primary
- **Backup Encryption**: All backups encrypted with AES-256
- **Retention**: 90 days operational, 7 years for compliance archives

### Q6.5: What is your uptime SLA?

**Answer**: 99.9% uptime SLA for production systems. Specific SLA terms documented in service agreement.

### Q6.6: How do you ensure high availability?

**Answer**:
- Multi-availability zone deployment
- Auto-scaling based on demand
- Load balancing across multiple instances
- Database replication with automatic failover
- Health monitoring with automatic instance replacement

---

## Incident Response

### Q7.1: Do you have a documented incident response plan?

**Answer**: Yes. Our incident response plan includes:
- Incident classification and severity levels
- Escalation procedures
- Communication protocols
- Containment and eradication procedures
- Recovery and post-incident review processes

### Q7.2: What are your breach notification timelines?

**Answer**:
- **Security Incidents**: Notification within 5 business days
- **Breaches**: Notification within 30 calendar days of discovery (per BAA)
- **Content**: Notification includes nature of breach, affected data types, mitigation steps, and contact information

### Q7.3: How do you detect security incidents?

**Answer**:
- Security Information and Event Management (SIEM) system
- Real-time alerting for suspicious activities
- 24/7 security monitoring
- Automated threat detection and response
- User behavior analytics

### Q7.4: When was your last security incident?

**Answer**: Information about specific security incidents is available under NDA to qualified prospects during the procurement process.

---

## Compliance and Certifications

### Q8.1: What compliance certifications do you hold?

**Answer**:

| Certification/Framework | Status | Notes |
|-------------------------|--------|-------|
| HIPAA | Compliant | BAA available for execution |
| SOC 2 Type II | In Progress | Expected completion Q2 2026 |
| ISO 27001 | Planned | On roadmap |
| HITRUST CSF | Under Evaluation | Evaluating certification timeline |

### Q8.2: Are you willing to sign a Business Associate Agreement (BAA)?

**Answer**: Yes. We execute HIPAA Business Associate Agreements with all customers who handle PHI. Our standard BAA template is available for review.

### Q8.3: Have you completed a SOC 2 Type II audit?

**Answer**: SOC 2 Type II audit is currently in progress with expected completion in Q2 2026. SOC 2 Type I report available upon request under NDA.

### Q8.4: Do you conduct regular third-party security assessments?

**Answer**: Yes.
- **Penetration Testing**: Annual third-party penetration tests
- **Vulnerability Assessments**: Quarterly external vulnerability assessments
- **Compliance Audits**: Annual HIPAA compliance assessments
- **Code Reviews**: Periodic third-party code security reviews

### Q8.5: Can you provide copies of audit reports?

**Answer**: Yes, the following are available under NDA:
- SOC 2 Type I report (Type II upon completion)
- Penetration test executive summary
- HIPAA compliance assessment summary

---

## Third-Party and Sub-processor Management

### Q9.1: Do you use sub-processors to process customer data?

**Answer**: Yes. We use a limited number of sub-processors for infrastructure and specific services.

### Q9.2: List of Sub-processors

**Answer**:

| Sub-processor | Service Provided | Data Processed | Location |
|---------------|------------------|----------------|----------|
| Cloud Infrastructure Provider | Infrastructure hosting, compute, storage | All customer data (encrypted) | United States |
| Email Service Provider | Transactional email delivery | Email addresses, notification content | United States |
| Monitoring Provider | Application performance monitoring | Anonymized telemetry data | United States |
| Support Platform | Customer support ticketing | Support communications (no PHI) | United States |

*Note: PHI is processed only on infrastructure within our direct control or on HIPAA-compliant sub-processor systems with executed BAAs.*

### Q9.3: How do you assess sub-processor security?

**Answer**:
- Security questionnaire and assessment before onboarding
- Review of SOC 2 or equivalent compliance reports
- BAA execution for any sub-processor handling PHI
- Annual reassessment of sub-processor security posture
- Contractual security requirements

### Q9.4: Will you notify us of sub-processor changes?

**Answer**: Yes. Customers are notified at least 30 days before any new sub-processor is engaged to process their data. Customers may object to new sub-processors per the terms of the service agreement.

---

## Security Governance

### Q10.1: Do you have documented security policies?

**Answer**: Yes. Our security policy framework includes:
- Information Security Policy
- Acceptable Use Policy
- Access Control Policy
- Data Classification Policy
- Incident Response Policy
- Business Continuity Policy
- Vendor Management Policy
- Change Management Policy

### Q10.2: How often are security policies reviewed?

**Answer**: All security policies are reviewed and updated annually, or more frequently when significant changes occur (regulatory updates, major incidents, organizational changes).

### Q10.3: Do you conduct security awareness training?

**Answer**: Yes.
- **Frequency**: Annual security awareness training for all employees
- **Content**: Phishing awareness, data handling, incident reporting, HIPAA requirements
- **Specialized Training**: Additional training for developers (secure coding) and administrators (system hardening)
- **Testing**: Periodic phishing simulations to assess effectiveness

### Q10.4: Do you have cyber insurance?

**Answer**: Yes. We maintain cyber liability insurance with coverage for data breaches, business interruption, and third-party claims. Certificate of insurance available upon request.

### Q10.5: Who is responsible for security at your organization?

**Answer**:
- **Executive Sponsor**: Chief Technology Officer (or equivalent)
- **Security Leadership**: Dedicated security team lead/manager
- **Operational Security**: Security operations team
- **Compliance**: Compliance officer for regulatory matters

---

## Additional Information

### Contact for Security Inquiries

For security-related questions or to request additional documentation:

- **Security Team**: security@upstream-healthcare.com
- **Compliance Inquiries**: compliance@upstream-healthcare.com

### Documentation Available Upon Request

The following documentation is available under NDA:
- SOC 2 Type I/II Report
- Penetration Test Executive Summary
- HIPAA Compliance Assessment
- Business Associate Agreement Template
- Security Architecture Diagrams
- Incident Response Plan Summary

---

*This questionnaire was last updated in February 2026. For the most current information, please contact our security team.*
