#!/bin/bash
# RAGGuard Spring Boot Orchestrator - Run Script

set -e

echo "🚀 Starting RAGGuard Spring Boot Orchestrator..."

# Check Java version
JAVA_VERSION=$(java -version 2>&1 | head -1 | cut -d'"' -f2 | cut -d'.' -f1)
if [ "$JAVA_VERSION" -lt 21 ]; then
    echo "❌ Java 21+ required. Current: $JAVA_VERSION"
    exit 1
fi
echo "✅ Java $JAVA_VERSION detected"

# Check if Maven wrapper exists
if [ ! -f "./mvnw" ]; then
    echo "📦 Creating Maven wrapper..."
    mvn -N io.takari:maven:wrapper -Dmaven=3.9.6
fi

# Make wrapper executable
chmod +x ./mvnw

# Build and run
echo "🔨 Building project..."
./mvnw clean package -DskipTests -q

echo "🏃 Starting application on http://localhost:8080/api"
echo "📋 Health checks:"
echo "   - Liveness:  http://localhost:8080/api/health/ping"
echo "   - Readiness: http://localhost:8080/api/health/ready"
echo ""
echo "🔐 Default users:"
echo "   - admin / admin123 (ADMIN)"
echo "   - analyst / analyst123 (ANALYST)"
echo "   - user / user123 (USER)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

./mvnw spring-boot:run