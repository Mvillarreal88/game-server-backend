# Game Server Backend - Task Backlog

## High Priority

- [ ] **Fix IP Address Persistence**
  - Add required annotations to LoadBalancer services
  - Test IP persistence across service recreation
  - Document the solution

- [ ] **Implement Server Activity Monitoring**
  - Complete the `check_server_activity` method
  - Add logic to detect inactive servers
  - Implement automatic shutdown for inactive servers

- [ ] **B2 Storage Integration**
  - Test B2 storage service with large files
  - Implement backup scheduling
  - Add error handling for network issues

## Medium Priority

- [ ] **Kubernetes Service Enhancements**
  - Add support for different game types
  - Implement resource quotas per user
  - Add support for custom server configurations

- [ ] **API Improvements**
  - Add endpoints for server statistics
  - Implement rate limiting
  - Add detailed server status information

- [ ] **Monitoring and Logging**
  - Set up centralized logging
  - Implement alerting for server issues
  - Create dashboard for server status

## Low Priority

- [ ] **Documentation**
  - Create API documentation
  - Document deployment process
  - Create user guide

- [ ] **Testing**
  - Add unit tests for all services
  - Set up integration testing
  - Create load testing scenarios

- [ ] **CI/CD Pipeline**
  - Set up GitHub Actions for testing
  - Implement automatic deployment
  - Add version tagging 