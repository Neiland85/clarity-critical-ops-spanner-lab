CREATE TABLE IdempotencyRecords (
  IdempotencyScope STRING(256) NOT NULL,
  IdempotencyKey STRING(256) NOT NULL,
  OperationType STRING(256) NOT NULL,
  RequestHash STRING(128) NOT NULL,
  Status STRING(32) NOT NULL,
  ResponsePayload JSON,
  ErrorPayload JSON,
  CreatedAt TIMESTAMP NOT NULL,
  UpdatedAt TIMESTAMP NOT NULL,
  LeaseToken STRING(64) NOT NULL,
  LeaseExpiresAt TIMESTAMP NOT NULL,
  Attempt INT64 NOT NULL,
  CompletedAt TIMESTAMP,
  FailedAt TIMESTAMP,
  LastExpiredAt TIMESTAMP
) PRIMARY KEY (IdempotencyScope, IdempotencyKey);
