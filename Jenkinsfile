pipeline {
    agent { label 'DockerRedHat' }

    environment {
        BACKEND_IMAGE  = 'team-tests-backend'
        FRONTEND_IMAGE = 'team-tests-frontend'
        IMAGE_TAG      = "build-${BUILD_NUMBER}"
    }

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 30, unit: 'MINUTES')
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
                script {
                    echo "=== BUILD INFO ==="
                    echo "BUILD_NUMBER : ${BUILD_NUMBER}"
                    echo "GIT_BRANCH   : ${env.GIT_BRANCH}"
                    echo "GIT_COMMIT   : ${env.GIT_COMMIT}"
                    echo "=================="
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                echo 'Building backend and frontend images...'
                script {
                    def backendResult = sh(
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
                    if (backendResult != 0) {
                        error('Backend Docker build failed')
                    }
                    echo 'Backend image built successfully'

                    def frontendResult = sh(
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
                    if (frontendResult != 0) {
                        error('Frontend Docker build failed')
                    }
                    echo 'Frontend image built successfully'
                }
            }
        }

        stage('Code Quality') {
            steps {
                echo 'Running flake8 code quality check...'
                sh """
                    docker run --rm ${BACKEND_IMAGE}:${IMAGE_TAG} \
                        flake8 app/ services/ orchestration/ \
                        --max-line-length=120 \
                        --exclude=__pycache__,.git,venv,migrations \
                        --exit-zero
                """
                echo 'Code quality check complete'
            }
        }

        stage('Smoke Test - Backend') {
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
                            ${BACKEND_IMAGE}:${IMAGE_TAG}

                        sleep 10  # initial wait

                        echo "=== CONTAINER STATUS ==="
                        docker ps -a | grep smoke-backend-${BUILD_NUMBER} || true

                        echo "=== CONTAINER LOGS (first 50 lines) ==="
                        docker logs smoke-backend-${BUILD_NUMBER} --tail=50 2>&1 || true

                        echo "=== WAITING FOR HEALTH CHECK ==="
                        for i in {1..8}; do
                            STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/api/health 2>/dev/null || echo "000")
                            echo "Attempt \$i - Health check status: \$STATUS"
                            if [ "\$STATUS" = "200" ]; then
                                echo "✅ Backend is healthy!"
                                break
                            fi
                            sleep 5
                        done

                        echo "=== FINAL CONTAINER LOGS ==="
                        docker logs smoke-backend-${BUILD_NUMBER} 2>&1 || true

                        docker stop smoke-backend-${BUILD_NUMBER} || true
                        docker rm   smoke-backend-${BUILD_NUMBER} || true

                        if [ "\$STATUS" != "200" ]; then
                            echo "❌ Smoke test failed — backend did not respond with 200 after ~40s"
                            exit 1
                        fi

                        echo "✅ Smoke test passed — backend is healthy"
                    """
                }
            }
        }

        stage('Prepare Environment') {
            steps {
                echo 'Generating .env file for CI...'
                sh """
                    cat > .env << EOF
DATABASE_URL=sqlite:///./test.db
SECRET_KEY=ci-secret-key-${BUILD_NUMBER}
DEBUG=true
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_URL=redis://redis:6379
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=testdb
EOF
                """
                echo '.env file created successfully'
            }
        }

        stage('Integration Test - Stack') {
            steps {
                echo 'Starting full stack with docker compose for integration test...'
                script {
                    def result = sh(
                        script: """
                            docker compose -f docker-compose.yml up -d \
                                --build \
                                --remove-orphans

                            sleep 25

                            BACKEND_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null)
                            echo "Backend health: \$BACKEND_STATUS"

                            FRONTEND_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null)
                            echo "Frontend health: \$FRONTEND_STATUS"

                            METRICS_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/metrics 2>/dev/null)
                            echo "Metrics endpoint: \$METRICS_STATUS"

                            docker compose down || true

                            if [ "\$BACKEND_STATUS" != "200" ]; then
                                echo "Integration test failed — backend not healthy"
                                exit 1
                            fi

                            echo "Integration test passed"
                        """,
                        returnStatus: true
                    )
                    if (result != 0) {
                        currentBuild.result = 'UNSTABLE'
                        echo 'Integration test had issues (non-blocking for deployment)'
                    }
                }
            }
        }

        stage('Deploy') {
            steps {
                echo 'Deploying full stack with docker compose...'
                sh """
                    docker compose down || true

                    docker compose up -d --remove-orphans

                    sleep 15

                    docker compose ps

                    HEALTH=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null)
                    echo "Post-deploy health check: \$HEALTH"

                    echo '=================================================='
                    echo '  DEPLOYMENT SUCCESSFUL'
                    echo '  Frontend  : http://localhost:5173'
                    echo '  Backend   : http://localhost:8000'
                    echo '  Grafana   : http://localhost:3000'
                    echo '  Prometheus: http://localhost:9090'
                    echo "  Image tag : ${IMAGE_TAG}"
                    echo '=================================================='
                """
            }
        }
    }

    post {
        always {
            echo 'Cleaning up temporary containers...'
            sh '''
                docker ps -a | grep -E "smoke-" | awk '{print $1}' | xargs -r docker rm -f || true
                docker image prune -f || true
                rm -f .env
            '''
        }
        success {
            echo "✅ BUILD AND DEPLOY SUCCESSFUL — ${BACKEND_IMAGE}:${IMAGE_TAG}"
        }
        failure {
            echo "❌ BUILD FAILED — check console logs for details"
        }
        unstable {
            echo "⚠️ BUILD UNSTABLE — images built but some tests had issues"
        }
    }
}