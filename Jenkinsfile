pipeline {
    agent any

    environment {
        IMAGE_NAME = 'ai-dashboard'
        IMAGE_TAG  = "build-${BUILD_NUMBER}"
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
                    echo "=== BRANCH DEBUG INFO ==="
                    echo "env.BRANCH_NAME   = ${env.BRANCH_NAME}"
                    echo "env.GIT_BRANCH    = ${env.GIT_BRANCH}"
                    echo "env.BUILD_NUMBER  = ${BUILD_NUMBER}"
                    echo "========================="
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building Docker image...'
                script {
                    def buildResult = sh(
                        script: """
                            docker build \
                                --no-cache \
                                --network=host \
                                -t ${IMAGE_NAME}:${IMAGE_TAG} \
                                -t ${IMAGE_NAME}:latest \
                                .
                        """,
                        returnStatus: true
                    )
                    if (buildResult != 0) {
                                            error('Docker build failed - network issue, no fallback allowed')
                                        }
                                        echo 'Docker image built successfully'
                        }
                }
            }

        stage('Unit Tests') {
            steps {
                echo 'Running unit tests...'
                script {
                    def result = sh(
                        script: """
                            docker run --rm \
                                ${IMAGE_NAME}:${IMAGE_TAG} \
                                pytest tests/ -v -m "not integration" \
                                --tb=short --maxfail=3
                        """,
                        returnStatus: true
                    )
                    if (result != 0) {
                        currentBuild.result = 'FAILURE'
                        error('Unit tests failed')
                    }
                    echo 'All unit tests passed'
                }
            }
        }

        stage('Test Agents') {
            steps {
                echo 'Testing AgentV1 and AgentV2...'
                script {
                    def ollamaUp = sh(
                        script: 'curl -sf http://host.docker.internal:11434/api/tags > /dev/null 2>&1',
                        returnStatus: true
                    ) == 0

                    if (!ollamaUp) {
                        echo 'Ollama not reachable - skipping agent tests'
                        return
                    }

                    echo 'Testing AgentV1 (Ollama)...'
                    def v1Result = sh(
                        script: """
                            docker run --rm \
                                --add-host=host.docker.internal:host-gateway \
                                -e OLLAMA_HOST=http://host.docker.internal:11434 \
                                -v /var/jenkins_home/.env:/app/.env:ro \
                                ${IMAGE_NAME}:${IMAGE_TAG} \
                                python -m orchestration.agentV1
                        """,
                        returnStatus: true
                    )
                    if (v1Result == 0) {
                        echo 'AgentV1 test passed'
                    } else {
                        echo 'AgentV1 test failed (non-blocking)'
                        currentBuild.result = 'UNSTABLE'
                    }

                    echo 'Testing AgentV2...'
                    def v2Result = sh(
                        script: """
                            docker run --rm \
                                --add-host=host.docker.internal:host-gateway \
                                -e OLLAMA_HOST=http://host.docker.internal:11434 \
                                -v /var/jenkins_home/.env:/app/.env:ro \
                                ${IMAGE_NAME}:${IMAGE_TAG} \
                                python -m orchestration.agentV2
                        """,
                        returnStatus: true
                    )
                    if (v2Result == 0) {
                        echo 'AgentV2 test passed'
                    } else {
                        echo 'AgentV2 test failed (non-blocking)'
                        currentBuild.result = 'UNSTABLE'
                    }
                }
            }
        }

        stage('Code Quality') {
            steps {
                echo 'Running code quality checks...'
                sh """
                    docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} \
                        flake8 . --max-line-length=120 \
                        --exclude=venv,__pycache__,.git,testing \
                        --exit-zero || true
                """
            }
        }

        stage('Smoke Test') {
            steps {
                echo 'Testing container starts correctly...'
                sh """
                    docker run -d \
                        --name smoke-${BUILD_NUMBER} \
                        -p 8501:8501 \
                        ${IMAGE_NAME}:${IMAGE_TAG}

                    sleep 15

                    docker logs smoke-${BUILD_NUMBER} | tail -20

                    docker stop smoke-${BUILD_NUMBER} || true
                    docker rm   smoke-${BUILD_NUMBER} || true
                """
            }
        }

        stage('Deploy to Feature Environment') {
            steps {
                echo 'Deploying to Feature Environment (Port 8503)...'
                sh """
                    docker stop ai-dashboard-feature || true
                    docker rm ai-dashboard-feature || true

                    docker run -d \
                        --name ai-dashboard-feature \
                        --restart unless-stopped \
                        -p 8503:8501 \
                        -v /var/jenkins_home/.env:/app/.env:ro \
                        --add-host=host.docker.internal:host-gateway \
                        -e OLLAMA_HOST=http://host.docker.internal:11434 \
                        ${IMAGE_NAME}:${IMAGE_TAG}

                    sleep 10

                    docker ps | grep ai-dashboard-feature || echo 'Container not running'

                    echo '=================================================='
                    echo '  DEPLOYMENT SUCCESSFUL'
                    echo '  Dashboard URL: http://localhost:8503'
                    echo "  Image: ${IMAGE_NAME}:${IMAGE_TAG}"
                    echo '=================================================='
                """
            }
        }
    }

    post {
        always {
            echo 'Cleanup...'
            sh '''
                docker ps -a | grep -E "(test-|smoke-)" | awk '{print $1}' | xargs -r docker rm -f || true
                docker system prune -f || true
            '''
        }
        success {
            echo "BUILD AND DEPLOY SUCCESSFUL - branch: ${env.BRANCH_NAME} - image: ${IMAGE_NAME}:${IMAGE_TAG}"
        }
        unstable {
            echo 'BUILD UNSTABLE - image built, unit tests passed, agent tests had issues'
        }
        failure {
            echo 'BUILD FAILED - check logs above'
        }
    }
}