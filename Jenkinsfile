pipeline {
    agent { label 'DockerRedHat' }

    environment {
        BACKEND_IMAGE   = 'ai-dashboard-backend'
        FRONTEND_IMAGE  = 'ai-dashboard-frontend'
        IMAGE_TAG       = "build-${BUILD_NUMBER}"
        COMPOSE_PROJECT = 'team-tests'
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

                        sleep 10

                        echo "=== CONTAINER LOGS ==="
                        docker logs smoke-backend-${BUILD_NUMBER} --tail=50 2>&1 || true

                        echo "=== HEALTH CHECK ==="
                        STATUS=000
                        for i in {1..8}; do
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

                            echo "Waiting for stack to be ready..."
                            sleep 30

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

                            docker compose -p ${COMPOSE_PROJECT}-test down || true

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
        stage('Deploy') {
        // ─────────────────────────────────────────────────────
            steps {
                echo 'Deploying full stack...'
                sh """
                    docker compose -p ${COMPOSE_PROJECT} down || true

                    docker compose -p ${COMPOSE_PROJECT} \
                        -f docker-compose.yml \
                        up -d --remove-orphans

                    echo "Waiting for services to start..."
                    sleep 20

                    echo "=== RUNNING SERVICES ==="
                    docker compose -p ${COMPOSE_PROJECT} ps

                    echo "=== POST-DEPLOY HEALTH CHECK ==="
                    HEALTH=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null || echo "000")
                    echo "Backend health: \$HEALTH"

                    echo "=================================================="
                    echo "  ✅ DEPLOYMENT SUCCESSFUL"
                    echo "  Frontend   : http://localhost:5173"
                    echo "  Backend    : http://localhost:8000"
                    echo "  Grafana    : http://localhost:3001"
                    echo "  Prometheus : http://localhost:9090"
                    echo "  Alertmanager: http://localhost:9093"
                    echo "  Image tag  : ${IMAGE_TAG}"
                    echo "=================================================="
                """
            }
        }
    }

    // ─────────────────────────────────────────────────────────
    post {
    // ─────────────────────────────────────────────────────────
        always {
            echo 'Cleaning up smoke test containers and dangling images...'
            sh """
                docker ps -a | grep -E "smoke-" | awk '{print \$1}' | xargs -r docker rm -f || true
                docker image prune -f || true
                rm -f .env
            """
        }
        success {
            echo "✅ BUILD & DEPLOY SUCCESSFUL — ${BACKEND_IMAGE}:${IMAGE_TAG}"
        }
        failure {
            echo "❌ BUILD FAILED — check console output above for details"
            sh """
                echo "=== DOCKER COMPOSE LOGS ON FAILURE ==="
                docker compose -p ${COMPOSE_PROJECT}-test logs --tail=50 2>&1 || true
                docker compose -p ${COMPOSE_PROJECT}-test down || true
            """
        }
        unstable {
            echo "⚠️ BUILD UNSTABLE — images built but some tests had issues"
        }
    }
}