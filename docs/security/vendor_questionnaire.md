# Vendor Security Assessment Questionnaire

## Upstream Healthcare, Inc. - Security Questionnaire Responses

*This document provides pre-filled responses to common vendor security assessment questions.*

---

## Company Information

| Question | Response |
|----------|----------|
| Company Legal Name | Upstream Healthcare, Inc. |
| Primary Contact | security@upstreamhealthcare.com |
| HIPAA Compliance | Yes |
| SOC 2 Certified | In Progress (Type I planned Q3 2026) |
| HITRUST Certified | Planned |

---

## 1. Information Security Management

**Q: Do you have a documented Information Security Policy?**
A: Yes. Our Information Security Policy is documented, approved by executive management, and reviewed annually.

**Q: Do you have a dedicated security team or officer?**
A: Yes. We have a HIPAA Security Officer and a dedicated security team.

**Q: How often do you conduct security awareness training?**
A: All employees complete security training upon hire and annually thereafter. Role-specific training is provided for personnel with access to PHI.

---

## 2. Access Control

**Q: How do you manage user access?**
A: We implement role-based access control (RBAC) with the principle of least privilege. Access is reviewed quarterly.

**Q: Do you require multi-factor authentication (MFA)?**
A: Yes. MFA is required for all user accounts accessing the platform.

**Q: How do you handle employee termination?**
A: Access is revoked within 4 hours of termination notification. All access tokens are immediately invalidated.

---

## 3. Data Protection

**Q: How is data encrypted at rest?**
A: All data is encrypted using AES-256 encryption. Database encryption uses PostgreSQL TDE. File storage uses AWS S3 server-side encryption.

**Q: How is data encrypted in transit?**
A: All data in transit uses TLS 1.3 (minimum TLS 1.2). HSTS is enforced for all web traffic.

**Q: Where is data stored?**
A: Data is stored in AWS data centers located in the United States (us-east-1 and us-west-2 regions).

**Q: Do you use subprocessors?**
A: Yes. Our subprocessors include:
- AWS (infrastructure)
- Stripe (payment processing)
All subprocessors have BAAs in place.

---

## 4. Network Security

**Q: Do you use firewalls?**
A: Yes. We use AWS Security Groups and Network ACLs for network segmentation and traffic control.

**Q: Do you have intrusion detection/prevention?**
A: Yes. We use AWS GuardDuty for threat detection and AWS WAF for web application firewall protection.

**Q: How do you protect against DDoS attacks?**
A: We use AWS Shield for DDoS protection at the infrastructure level.

---

## 5. Application Security

**Q: Do you perform security testing?**
A: Yes. We perform:
- Weekly automated vulnerability scans
- Annual third-party penetration testing
- Daily dependency vulnerability scanning
- Code security reviews for all changes

**Q: How do you handle security vulnerabilities?**
A: Critical vulnerabilities are patched within 24 hours. High-severity within 7 days. All others within 30 days.

**Q: Do you have a secure development lifecycle?**
A: Yes. Our SDLC includes security requirements, threat modeling, code review, security testing, and deployment security.

---

## 6. Incident Response

**Q: Do you have an incident response plan?**
A: Yes. Our incident response plan follows NIST guidelines and is tested quarterly through tabletop exercises.

**Q: What is your breach notification timeline?**
A: Customers are notified within 24 hours of discovery of a security incident involving their data.

**Q: Do you carry cyber insurance?**
A: Yes. We maintain cyber liability insurance coverage.

---

## 7. Business Continuity

**Q: Do you have a disaster recovery plan?**
A: Yes. Our DR plan includes:
- Multi-region deployment
- Automated failover
- Daily backups with 30-day retention
- Quarterly DR testing

**Q: What is your RTO/RPO?**
A: Recovery Time Objective (RTO): 4 hours
Recovery Point Objective (RPO): 1 hour

**Q: What is your uptime SLA?**
A: 99.9% availability for production systems.

---

## 8. Compliance

**Q: Are you HIPAA compliant?**
A: Yes. We implement all required administrative, physical, and technical safeguards. We provide BAAs to all customers.

**Q: Are you SOC 2 certified?**
A: SOC 2 Type I certification is planned for Q3 2026. SOC 2 Type II is planned for Q1 2027.

**Q: Do you conduct regular risk assessments?**
A: Yes. We conduct annual comprehensive risk assessments and ongoing risk management activities.

---

## 9. Physical Security

**Q: Where are your servers located?**
A: Our infrastructure is hosted in AWS data centers that are SOC 2, ISO 27001, and HIPAA compliant.

**Q: Do you have physical access controls?**
A: AWS data centers implement comprehensive physical security including biometric access, 24/7 security guards, and video surveillance.

---

## 10. Audit and Logging

**Q: Do you maintain audit logs?**
A: Yes. We maintain comprehensive audit logs of all access to PHI including who, what, when, and where.

**Q: How long do you retain logs?**
A: Audit logs are retained for 6 years per HIPAA requirements.

**Q: Can customers access their audit logs?**
A: Yes. Customers can access their audit logs through our platform or via API.

---

## Additional Documentation Available

Upon request, we can provide:
- Security policies and procedures (under NDA)
- Penetration test executive summary
- SOC 2 report (when available)
- Compliance certifications
- Insurance certificates

**Contact**: security@upstreamhealthcare.com

---

*Last Updated: February 2026*
