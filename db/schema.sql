CREATE TABLE IdempotencyRegistry (
    IdempotencyKey STRING(64) NOT NULL,
    UserId STRING(36) NOT NULL,
    ExecutionStatus STRING(16) NOT NULL, -- PENDING, COMPLETED, FAILED
    ResponsePayload BYTES(MAX),
    CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (IdempotencyKey);

-- Índice para auditorías rápidas por usuario y fecha de creación
CREATE INDEX IdempotencyByUserAndDate 
ON IdempotencyRegistry (UserId, CreatedAt DESC);
