# RAGGuard Spring Boot Orchestrator

Spring Boot 3.2 backend that orchestrates the RAGGuard FastAPI services. Acts as a gateway providing JWT authentication, role-based access control, and a unified API layer.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Client    │────▶│ Spring Boot      │────▶│  FastAPI    │
│  (Frontend) │     │ Orchestrator     │     │  Backend    │
│             │     │ (Port 8080)      │     │ (Port 8000) │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    │  SQLite DB  │
                    │  (Users,    │
                    │   Perms)    │
                    └─────────────┘
```

## Features

- **JWT Authentication** - Compatible with FastAPI JWT format
- **Role-Based Access Control** - ADMIN, ANALYST, USER roles
- **Reactive FastAPI Client** - Non-blocking WebClient with connection pooling
- **Document Management** - Upload, list, search, delete, reindex
- **Chat & Conversations** - Streaming and non-streaming chat
- **Health Checks** - Kubernetes-ready liveness/readiness probes
- **Auto-initialization** - Creates default users on first run

## Quick Start

### Prerequisites
- Java 21+
- Maven 3.9+ (or use included wrapper)
- FastAPI backend running on `http://localhost:8000`

### Run

```bash
# Make executable and run
chmod +x run.sh
./run.sh

# Or manually:
./mvnw spring-boot:run
```

### Default Users
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 (or `ADMIN_PASSWORD`) | ADMIN |
| analyst | analyst123 (or `ANALYST_PASSWORD`) | ANALYST |
| user | user123 (or `USER_PASSWORD`) | USER |

Passwords are overridable via environment variables (`ADMIN_PASSWORD`, `ANALYST_PASSWORD`, `USER_PASSWORD`).

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login, returns JWT |
| POST | `/api/auth/register` | Register new user |
| GET | `/api/auth/me` | Current user info |
| POST | `/api/auth/validate` | Validate token |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Non-streaming chat |
| POST | `/api/chat/stream` | Streaming chat (SSE) |
| POST | `/api/chat/conversations` | Create conversation |
| GET | `/api/chat/conversations` | List conversations |
| GET | `/api/chat/conversations/{id}/messages` | Get messages |
| POST | `/api/chat/feedback` | Submit feedback |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/documents/upload` | Upload document (multipart) |
| GET | `/api/documents` | List documents (paginated) |
| GET | `/api/documents/{id}` | Get document |
| DELETE | `/api/documents/{id}` | Delete document |
| PATCH | `/api/documents/{id}` | Update document metadata |
| POST | `/api/documents/search` | Search documents |
| POST | `/api/documents/reindex` | Trigger reindex (ADMIN/ANALYST) |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health/ping` | Liveness probe |
| GET | `/api/health/ready` | Readiness probe (checks FastAPI) |
| GET | `/api/health/live` | Alive probe |

## Configuration

Edit `src/main/resources/application.yml`:

```yaml
server:
  port: 8080
  servlet:
    context-path: /api

ragguard:
  fastapi:
    base-url: http://localhost:8000  # FastAPI backend URL
    timeout: 30s
  jwt:
    secret: ${JWT_SECRET_KEY}        # Set in environment
    expiration: 3600000              # 1 hour
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | (required) | JWT signing secret |
| `DATABASE_URL` | `jdbc:sqlite:data/ragguard.db` | SQLite database path |

## Project Structure

```
src/main/java/com/ragguard/orchestrator/
├── client/           # FastAPI WebClient
├── config/           # Configuration classes
├── controller/       # REST controllers
├── model/            # JPA entities & DTOs
│   └── dto/          # Request/Response DTOs
├── repository/       # Spring Data JPA repositories
├── security/         # JWT filter, security config
├── service/          # Business logic
└── OrchestratorApplication.java
```

## Building

```bash
# Build JAR
./mvnw clean package -DskipTests

# Run JAR
java -jar target/orchestrator-1.0.0-SNAPSHOT.jar
```

## Docker

```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/orchestrator-*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

## Security Notes

- JWT tokens are validated on every request
- Raw JWT is stored in `UserPrincipal` for downstream FastAPI calls
- CORS configured for localhost:3000, localhost:8080, 127.0.0.1:8000
- All endpoints except `/auth/**` and `/health/**` require authentication
- Role-based method security with `@PreAuthorize`
- **Self-registration cannot grant elevated roles** — `/api/auth/register` only allows `USER`/`ANALYST`; `ADMIN` is reserved for `DataInitializer` (CWE-269/CWE-285)
- Actuator is not exposed anonymously: only `/actuator/health` is public, everything else requires auth
- `JWT_SECRET_KEY` should always be set in the environment — without it, a random key is used and all tokens are invalidated on restart