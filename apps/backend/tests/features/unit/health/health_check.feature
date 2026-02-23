Feature: Health Check
  As a DevOps engineer
  I want to check the service health status
  So that I can monitor the system availability

  Scenario: All services are healthy
    Given the database is reachable
    When I perform a health check
    Then the status should be "healthy"
    And the database status should be "connected"

  Scenario: Database is unreachable
    Given the database is not reachable
    When I perform a health check
    Then the status should be "unhealthy"
    And the database status should be "disconnected"
