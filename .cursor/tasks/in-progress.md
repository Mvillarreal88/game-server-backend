# Game Server Backend - In Progress Tasks

## Currently Working On

- [ ] **Fix Kubernetes Service Indentation**
  - Fix indentation in `check_server_activity` method
  - Test the method with running servers
  - Status: Code fixed, needs testing

- [ ] **Implement Static IP Solution**
  - Add annotations for static IPs in LoadBalancer services
  - Update `create_game_service` method
  - Status: Solution identified, implementation pending

- [ ] **B2SDK Integration**
  - Fix import issues with B2SDK
  - Test file upload/download functionality
  - Status: Package added to requirements.txt, needs testing

## Blocked Tasks

- [ ] **Server Auto-Scaling**
  - Waiting for AKS cluster metrics configuration
  - Need to determine scaling thresholds
  - Status: Blocked by infrastructure setup

- [ ] **Database Schema Updates**
  - Need to finalize server metadata requirements
  - Waiting for feedback on proposed schema
  - Status: Pending review

## Next Up

- [ ] **Implement Server Backup System**
  - Design backup schedule
  - Implement backup triggers
  - Create restore functionality
  
- [ ] **API Authentication Improvements**
  - Add token-based authentication
  - Implement role-based access control
  - Set up Azure AD integration 