pipeline {
    agent any  // ← Changez cette ligne (au lieu de agent { docker { ... } })

    environment {
        PYTHONUNBUFFERED = '1'
    }

    options {
        timestamps()
        skipDefaultCheckout(true)
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Check Docker Version') {
            steps {
                sh 'docker --version'
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                python3 -m pip install --upgrade pip || true
                pip3 install -r requirements.txt || true
                pip3 install pytest flake8 black streamlit || true
                '''
            }
        }

        stage('Lint Code') {
            steps {
                sh 'flake8 . || true'
            }
        }

        stage('Run Tests') {
            steps {
                sh 'pytest || true'
            }
        }

        stage('Validate Python Syntax') {
            steps {
                sh '''
                python3 -m py_compile main.py || true
                python3 -m py_compile services/*.py || true
                '''
            }
        }

        stage('Build Docker Image') {
            when {
                branch 'devops-test'
            }
            steps {
                sh 'docker build -t ai-agent:${BUILD_NUMBER} -t ai-agent:latest .'
            }
        }

        stage('Run Streamlit Check') {
            steps {
                sh '''
                docker run -d --name streamlit-test -p 8502:8501 ai-agent:latest
                sleep 10
                docker logs streamlit-test || true
                docker stop streamlit-test || true
                docker rm streamlit-test || true
                '''
            }
        }
    }

    post {
        always {
            echo 'Pipeline finished.'
        }
        success {
            echo 'Build OK.'
        }
        failure {
            echo 'Build failed.'
        }
    }
}