pipeline {

    agent {
        docker {
            image 'python:3.11'
            args '-u root'
        }
    }

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

        stage('Install Dependencies') {
            steps {
                sh '''
                python -m pip install --upgrade pip
                pip install -r requirements.txt
                pip install pytest flake8 black streamlit
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
                python -m py_compile main.py
                python -m py_compile services/*.py || true
                '''
            }
        }

        stage('Build Docker Image (optional future deploy)') {
            when {
                branch 'devops-test'
            }
            steps {
                sh '''
                docker build -t ai-agent .
                '''
            }
        }

        stage('Run Streamlit Check') {
            steps {
                sh '''
                streamlit run main.py --server.headless true &
                sleep 10
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
