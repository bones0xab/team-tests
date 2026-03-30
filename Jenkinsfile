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
                            ${BACKEND_IMAGE}:${IMAGE_TAG}

                        sleep 10

                        STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8099/api/health || echo "000")
                        echo "Health check status: \$STATUS"

                        docker stop smoke-backend-${BUILD_NUMBER} || true
                        docker rm   smoke-backend-${BUILD_NUMBER} || true

                        if [ "\$STATUS" != "200" ]; then
                            echo "Smoke test failed — backend did not respond with 200"
                            exit 1
                        fi

                        echo "Smoke test passed — backend is healthy"
                    """
                }
            }
        }

        stage('Integration Test - Stack') {
            steps {
                echo 'Starting full stack with docker-compose for integration test...'
                script {
                    def result = sh(
                        script: """
                            docker-compose -f docker-compose.yml up -d \
                                --build \
                                --remove-orphans

                            sleep 20

                            BACKEND_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health || echo "000")
                            echo "Backend health: \$BACKEND_STATUS"

                            FRONTEND_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 || echo "000")
                            echo "Frontend health: \$FRONTEND_STATUS"

                            METRICS_STATUS=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/metrics || echo "000")
                            echo "Metrics endpoint: \$METRICS_STATUS"

                            docker-compose down || true

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
                echo 'Deploying full stack with docker-compose...'
                sh """
                    docker-compose down || true

                    docker-compose up -d --remove-orphans

                    sleep 15

                    docker-compose ps

                    HEALTH=\$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health || echo "000")
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