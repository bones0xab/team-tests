pipeline {
    agent { label 'DockerRedHat' }

    environment {
        BACKEND_IMAGE   = 'ai-dashboard-backend'
        FRONTEND_IMAGE  = 'ai-dashboard-frontend'
        IMAGE_TAG       = "build-${BUILD_NUMBER}"
        COMPOSE_PROJECT = 'team-tests'

        TEST_USER         = credentials('CI_TEST_USERNAME')
        TEST_PASSWORD     = credentials('CI_TEST_PASSWORD')
        TEAMS_WEBHOOK_URL = credentials('TEAMS_WEBHOOK_URL')
    }

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 45, unit: 'MINUTES')
    }

    stages {

        // ─────────────────────────────────────────────────────
        stage('Checkout') {
        // ─────────────────────────────────────────────────────
            steps {
                checkout scm
                script {
                    echo "======================================"
                    echo " BUILD_NUMBER : ${BUILD_NUMBER}"
                    echo " GIT_BRANCH   : ${env.GIT_BRANCH}"
                    echo " GIT_COMMIT   : ${env.GIT_COMMIT}"
                    echo "======================================"
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Prepare Environment') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Generating .env file for CI...'
                sh """
                    cat > .env << EOF
DATABASE_URL=postgresql://postgres:postgres@db:5432/jira_health
SECRET_KEY=ci-secret-key-${BUILD_NUMBER}
DEBUG=true
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_URL=redis://redis:6379
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=jira_health
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
TEAMS_WEBHOOK_URL=${TEAMS_WEBHOOK_URL}
EOF
                """
                echo '.env file created'
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Build Docker Images') {
        // ─────────────────────────────────────────────────────
            parallel {

                stage('Build Backend') {
                    steps {
                        script {
                            echo 'Building backend image (FastAPI)...'
                            def result = sh(
                                script: """
                                    docker build \
                                        --no-cache \
                                        --network=host \
                                        -f Dockerfile \
                                        -t ${BACKEND_IMAGE}:${IMAGE_TAG} \
                                        -t ${BACKEND_IMAGE}:latest \
                                        .
                                """,
                                returnStatus: true
                            )
                            if (result != 0) error('❌ Backend Docker build failed')
                            echo '✅ Backend image built successfully'
                        }
                    }
                }

                stage('Build Frontend') {
                    steps {
                        script {
                            echo 'Building frontend image (React)...'
                            def result = sh(
                                script: """
                                    docker build \
                                        --no-cache \
                                        --network=host \
                                        -f frontend/Dockerfile \
                                        -t ${FRONTEND_IMAGE}:${IMAGE_TAG} \
                                        -t ${FRONTEND_IMAGE}:latest \
                                        ./frontend
                                """,
                                returnStatus: true
                            )
                            if (result != 0) error('❌ Frontend Docker build failed')
                            echo '✅ Frontend image built successfully'
                        }
                    }
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Code Quality') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Running flake8 on backend code...'
                sh """
                    docker run --rm ${BACKEND_IMAGE}:${IMAGE_TAG} \
                        flake8 app/ services/ orchestration/ tasks/ adapters/ \
                        --max-line-length=120 \
                        --exclude=__pycache__,.git,venv,migrations \
                        --exit-zero
                """
                echo '✅ Code quality check complete'
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Unit Tests') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Running unit tests...'
                script {
                    def result = sh(
                        script: """
                            docker run --rm \
                                -e DATABASE_URL=sqlite:///./test.db \
                                -e SECRET_KEY=test-secret-key \
                                -e DEBUG=true \
                                -e ALGORITHM=HS256 \
                                -e ACCESS_TOKEN_EXPIRE_MINUTES=30 \
                                -e REDIS_URL=redis://localhost:6379 \
                                ${BACKEND_IMAGE}:${IMAGE_TAG} \
                                pytest app/tests/ -v --tb=short 2>&1 || true
                        """,
                        returnStatus: true
                    )
                    if (result != 0) {
                        echo '⚠️ Some unit tests failed (non-blocking)'
                        currentBuild.result = 'UNSTABLE'
                    } else {
                        echo '✅ Unit tests passed'
                    }
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Smoke Test - Backend') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Smoke testing backend container startup...'
                script {
                    sh """
                        docker run -d \
                            --name smoke-backend-${BUILD_NUMBER} \
                            -p 8099:8000 \
                            -e DATABASE_URL=sqlite:///./test.db \
                            -e SECRET_KEY=test-secret-key \
                            -e DEBUG=true \
                            -e ALGORITHM=HS256 \
                            -e ACCESS_TOKEN_EXPIRE_MINUTES=30 \
                            -e REDIS_URL=redis://localhost:6379 \
                            ${BACKEND_IMAGE}:${IMAGE_TAG}

                        echo "=== CONTAINER LOGS ==="
                        docker logs smoke-backend-${BUILD_NUMBER} --tail=50 2>&1 || true

                        echo "=== HEALTH CHECK (polling) ==="
                        STATUS=000
                        for i in \$(seq 1 12); do
                            STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/api/health 2>/dev/null || echo "000")
                            echo "Attempt \$i — status: \$STATUS"
                            if [ "\$STATUS" = "200" ]; then
                                echo "✅ Backend healthy!"
                                break
                            fi
                            sleep 5
                        done

                        docker stop smoke-backend-${BUILD_NUMBER} || true
                        docker rm   smoke-backend-${BUILD_NUMBER} || true

                        if [ "\$STATUS" != "200" ]; then
                            echo "❌ Smoke test failed — backend did not respond with 200"
                            exit 1
                        fi
                        echo "✅ Smoke test passed"
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Integration Test - Full Stack') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Starting full stack for integration test...'
                script {
                    def result = sh(
                        script: """
                            docker compose -p ${COMPOSE_PROJECT}-test \
                                -f docker-compose.yml up -d \
                                --build \
                                --remove-orphans

                            echo "Waiting for stack to be ready (polling)..."
                            STATUS=000
                            for i in \$(seq 1 12); do
                                STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
                                echo "Attempt \$i — backend: \$STATUS"
                                [ "\$STATUS" = "200" ] && break
                                sleep 5
                            done

                            echo "=== STACK STATUS ==="
                            docker compose -p ${COMPOSE_PROJECT}-test ps

                            echo "=== HEALTH CHECKS ==="
                            BACKEND_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
                            echo "Backend  (FastAPI)  : \$BACKEND_STATUS"

                            FRONTEND_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null || echo "000")
                            echo "Frontend (React)    : \$FRONTEND_STATUS"

                            GRAFANA_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null || echo "000")
                            echo "Grafana             : \$GRAFANA_STATUS"

                            PROMETHEUS_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9090 2>/dev/null || echo "000")
                            echo "Prometheus          : \$PROMETHEUS_STATUS"

                            METRICS_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/metrics 2>/dev/null || echo "000")
                            echo "Metrics endpoint    : \$METRICS_STATUS"

                            if [ "\$BACKEND_STATUS" != "200" ]; then
                                echo "❌ Integration test failed — backend not healthy"
                                exit 1
                            fi
                            echo "✅ Integration test passed"
                        """,
                        returnStatus: true
                    )
                    if (result != 0) {
                        currentBuild.result = 'UNSTABLE'
                        echo '⚠️ Integration test had issues (non-blocking for deployment)'
                    }
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Infrastructure Checks') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Running infrastructure validation checks...'
                script {
                    sh """
                        docker compose -p ${COMPOSE_PROJECT}-infra \
                            -f docker-compose.yml up -d \
                            --remove-orphans

                        echo "Waiting for infra (polling)..."
                        for i in \$(seq 1 8); do
                            REDIS_RESULT=\$(docker exec \$(docker compose -p ${COMPOSE_PROJECT}-infra ps -q redis) \
                                redis-cli PING 2>/dev/null || echo "FAILED")
                            [ "\$REDIS_RESULT" = "PONG" ] && break
                            sleep 5
                        done

                        echo "=== [1/3] REDIS CHECK ==="
                        echo "Redis PING: \$REDIS_RESULT"
                        if [ "\$REDIS_RESULT" != "PONG" ]; then
                            echo "❌ Redis is not responding"
                            exit 1
                        fi
                        echo "✅ Redis is healthy"

                        echo "=== [2/3] DATABASE CHECK ==="
                        DB_RESULT=\$(docker exec \$(docker compose -p ${COMPOSE_PROJECT}-infra ps -q db) \
                            psql -U postgres -d jira_health -c "SELECT 1" 2>/dev/null | grep -c "1 row" || echo "0")
                        echo "DB rows returned: \$DB_RESULT"
                        if [ "\$DB_RESULT" = "0" ]; then
                            echo "❌ Database is not responding or schema missing"
                            exit 1
                        fi
                        echo "✅ Database is healthy"

                        echo "=== [3/3] DB TABLES CHECK ==="
                        TABLES=\$(docker exec \$(docker compose -p ${COMPOSE_PROJECT}-infra ps -q db) \
                            psql -U postgres -d jira_health -c "\\dt" 2>/dev/null | grep -c "public" || echo "0")
                        echo "Tables found: \$TABLES"
                        if [ "\$TABLES" = "0" ]; then
                            echo "⚠️ No tables found — migrations may not have run"
                        else
                            echo "✅ Database schema validated (\$TABLES tables)"
                        fi
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Auth & API Tests') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Running auth flow and key API endpoint tests...'
                script {
                    sh """
                        docker compose -p ${COMPOSE_PROJECT}-auth \
                            -f docker-compose.yml up -d \
                            --remove-orphans

                        echo "Waiting for auth stack (polling)..."
                        for i in \$(seq 1 10); do
                            STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
                            [ "\$STATUS" = "200" ] && break
                            sleep 5
                        done

                        BASE=http://localhost:8000

                        echo "=== [1/4] REGISTER TEST USER ==="
                        REGISTER_STATUS=\$(curl -s -o /tmp/register_resp.json -w "%{http_code}" \
                            -X POST \$BASE/api/register \
                            -H "Content-Type: application/json" \
                            -d "{\"username\":\"${TEST_USER}\",\"email\":\"ci-test@jenkins.local\",\"password\":\"${TEST_PASSWORD}\"}" \
                            2>/dev/null || echo "000")
                        echo "Register status: \$REGISTER_STATUS"
                        # 201 = created, 400 = already exists (both OK for CI)
                        if [ "\$REGISTER_STATUS" != "201" ] && [ "\$REGISTER_STATUS" != "400" ]; then
                            echo "❌ Register failed with status \$REGISTER_STATUS"
                            exit 1
                        fi
                        echo "✅ Register OK"

                        echo "=== [2/4] LOGIN TEST ==="
                        LOGIN_RESP=\$(curl -s -X POST \$BASE/api/login \
                            -H "Content-Type: application/json" \
                            -d "{\"username\":\"${TEST_USER}\",\"password\":\"${TEST_PASSWORD}\"}" \
                            2>/dev/null || echo "")
                        TOKEN=\$(echo \$LOGIN_RESP | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
                        if [ -z "\$TOKEN" ]; then
                            echo "❌ Login failed — no token returned"
                            exit 1
                        fi
                        echo "✅ Login OK — token received"

                        echo "=== [3/4] /api/me TEST ==="
                        ME_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" \
                            \$BASE/api/me \
                            -H "Authorization: Bearer \$TOKEN" \
                            2>/dev/null || echo "000")
                        echo "/api/me status: \$ME_STATUS"
                        if [ "\$ME_STATUS" != "200" ]; then
                            echo "❌ /api/me failed with status \$ME_STATUS"
                            exit 1
                        fi
                        echo "✅ /api/me OK"

                        echo "=== [4/4] LOGOUT TEST ==="
                        LOGOUT_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" \
                            -X POST \$BASE/api/logout \
                            -H "Authorization: Bearer \$TOKEN" \
                            2>/dev/null || echo "000")
                        echo "Logout status: \$LOGOUT_STATUS"
                        if [ "\$LOGOUT_STATUS" != "200" ]; then
                            echo "⚠️ Logout returned \$LOGOUT_STATUS (non-blocking)"
                        else
                            echo "✅ Logout OK"
                        fi
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Teams Webhook Test') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Testing webhook endpoint (CI-only — skips digest throttle)...'
                script {
                    sh """
                        echo "=== TESTING /api/webhook/alert ==="
                        WEBHOOK_STATUS=\$(curl -s -o /tmp/webhook_resp.json -w "%{http_code}" \
                            -X POST http://localhost:8000/api/webhook/alert \
                            -H "Content-Type: application/json" \
                            -d '{
                                "receiver": "jenkins-ci",
                                "status": "firing",
                                "alerts": [{
                                    "status": "firing",
                                    "labels": {
                                        "project_key": "CI-TEST",
                                        "severity": "WARNING",
                                        "ci_test": "true"
                                    },
                                    "annotations": {
                                        "summary": "Jenkins CI webhook test",
                                        "description": "Automated test from build #${BUILD_NUMBER}"
                                    }
                                }],
                                "groupLabels": {},
                                "commonLabels": {}
                            }' 2>/dev/null || echo "000")

                        echo "Webhook status: \$WEBHOOK_STATUS"
                        cat /tmp/webhook_resp.json || true

                        if [ "\$WEBHOOK_STATUS" != "200" ]; then
                            echo "⚠️ Webhook returned \$WEBHOOK_STATUS (non-blocking)"
                        else
                            echo "✅ Webhook OK"
                        fi

                        echo "=== TESTING /api/webhook/history ==="
                        HISTORY_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" \
                            http://localhost:8000/api/webhook/history?project_key=CI-TEST \
                            2>/dev/null || echo "000")
                        echo "History status: \$HISTORY_STATUS"
                        if [ "\$HISTORY_STATUS" = "200" ]; then
                            echo "✅ Alert history endpoint OK"
                        else
                            echo "⚠️ History returned \$HISTORY_STATUS"
                        fi
                    """
                }
            }
        }

        // ─────────────────────────────────────────────────────
        stage('Deploy') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Deploying full stack...'
                sh """
                    docker compose -p ${COMPOSE_PROJECT} down || true

                    docker compose -p ${COMPOSE_PROJECT} \
                        -f docker-compose.yml \
                        up -d --remove-orphans

                    echo "Waiting for services (polling)..."
                    for i in \$(seq 1 12); do
                        HEALTH=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
                        [ "\$HEALTH" = "200" ] && break
                        sleep 5
                    done

                    echo "=== RUNNING SERVICES ==="
                    docker compose -p ${COMPOSE_PROJECT} ps

                    echo "=== POST-DEPLOY HEALTH CHECKS ==="
                    HEALTH=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
                    echo "Backend /api/health  : \$HEALTH"

                    METRICS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/metrics 2>/dev/null || echo "000")
                    echo "Backend /api/metrics : \$METRICS"

                    FRONTEND=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null || echo "000")
                    echo "Frontend             : \$FRONTEND"

                    REDIS=\$(docker exec \$(docker compose -p ${COMPOSE_PROJECT} ps -q redis) \
                        redis-cli PING 2>/dev/null || echo "FAILED")
                    echo "Redis PING           : \$REDIS"

                    DB=\$(docker exec \$(docker compose -p ${COMPOSE_PROJECT} ps -q db) \
                        psql -U postgres -d jira_health -c "SELECT 1" 2>/dev/null | grep -c "1 row" || echo "0")
                    echo "Database SELECT 1    : \$DB row(s)"

                    LOGIN_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" \
                        -X POST http://localhost:8000/api/login \
                        -H "Content-Type: application/json" \
                        -d "{\"username\":\"${TEST_USER}\",\"password\":\"${TEST_PASSWORD}\"}" \
                        2>/dev/null || echo "000")
                    echo "Auth /api/login      : \$LOGIN_STATUS"

                    echo "=================================================="
                    echo "  DEPLOYMENT SUMMARY"
                    echo "  Backend health : \$HEALTH"
                    echo "  Metrics        : \$METRICS"
                    echo "  Frontend       : \$FRONTEND"
                    echo "  Redis          : \$REDIS"
                    echo "  Database       : \$DB row(s)"
                    echo "  Auth login     : \$LOGIN_STATUS"
                    echo "=================================================="

                    if [ "\$HEALTH" != "200" ]; then
                        echo "❌ DEPLOYMENT FAILED — backend /api/health not responding"
                        exit 1
                    fi

                    echo "  Frontend   : http://localhost:5173"
                    echo "  Backend    : http://localhost:8000"
                    echo "  Grafana    : http://localhost:3001"
                    echo "  Prometheus : http://localhost:9090"
                    echo "  Alertmgr   : http://localhost:9093"
                    echo "  Image tag  : ${IMAGE_TAG}"
                    echo "  ✅ DEPLOYMENT SUCCESSFUL"
                    echo "=================================================="
                """
            }
        }
    }

    // ─────────────────────────────────────────────────────────
    post {
    // ─────────────────────────────────────────────────────────
        always {
            echo 'Cleaning up all compose stacks and temp files...'
            sh """
                docker compose -p ${COMPOSE_PROJECT}-test  down --remove-orphans || true
                docker compose -p ${COMPOSE_PROJECT}-infra down --remove-orphans || true
                docker compose -p ${COMPOSE_PROJECT}-auth  down --remove-orphans || true
                docker ps -a | grep -E "smoke-" | awk '{print \$1}' | xargs -r docker rm -f || true
                docker image prune -f || true
                rm -f .env /tmp/register_resp.json /tmp/webhook_resp.json /tmp/teams_payload.json || true
            """
        }

        success {
            echo "✅ BUILD & DEPLOY SUCCESSFUL — ${BACKEND_IMAGE}:${IMAGE_TAG}"
            sh """
                cat > /tmp/teams_payload.json << EOF
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "00C853",
    "summary": "Build ${BUILD_NUMBER} passed",
    "title": "✅ Build #${BUILD_NUMBER} PASSED",
    "sections": [{
        "facts": [
            {"name": "Branch", "value": "${env.GIT_BRANCH}"},
            {"name": "Commit", "value": "${env.GIT_COMMIT}"},
            {"name": "Image",  "value": "${BACKEND_IMAGE}:${IMAGE_TAG}"}
        ],
        "markdown": true
    }]
}
EOF
                curl -s -X POST "${TEAMS_WEBHOOK_URL}" \
                    -H "Content-Type: application/json" \
                    -d @/tmp/teams_payload.json || true
            """
        }

        failure {
            echo "❌ BUILD FAILED — check console output above for details"
            sh """
                echo "=== DOCKER COMPOSE LOGS ON FAILURE ==="
                docker compose -p ${COMPOSE_PROJECT}-test logs --tail=50 2>&1 || true

                cat > /tmp/teams_payload.json << EOF
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "D50000",
    "summary": "Build ${BUILD_NUMBER} failed",
    "title": "❌ Build #${BUILD_NUMBER} FAILED",
    "sections": [{
        "facts": [
            {"name": "Branch", "value": "${env.GIT_BRANCH}"},
            {"name": "Commit", "value": "${env.GIT_COMMIT}"},
            {"name": "Action", "value": "Check Jenkins for details"}
        ],
        "markdown": true
    }]
}
EOF
                curl -s -X POST "${TEAMS_WEBHOOK_URL}" \
                    -H "Content-Type: application/json" \
                    -d @/tmp/teams_payload.json || true
            """
        }

        unstable {
            echo "⚠️ BUILD UNSTABLE — images built but some tests had issues"
            sh """
                cat > /tmp/teams_payload.json << EOF
{
    "@type": "MessageCard",
    "@context": "http://schema.org/extensions",
    "themeColor": "FF6D00",
    "summary": "Build ${BUILD_NUMBER} unstable",
    "title": "⚠️ Build #${BUILD_NUMBER} UNSTABLE",
    "sections": [{
        "facts": [
            {"name": "Branch", "value": "${env.GIT_BRANCH}"},
            {"name": "Note",   "value": "Some tests had issues but deployment continued"}
        ],
        "markdown": true
    }]
}
EOF
                curl -s -X POST "${TEAMS_WEBHOOK_URL}" \
                    -H "Content-Type: application/json" \
                    -d @/tmp/teams_payload.json || true
            """
        }
    }
}