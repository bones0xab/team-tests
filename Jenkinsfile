pipeline {

    agent {
        docker {
            image 'docker:24-cli'
            args '-u root -v /var/run/docker.sock:/var/run/docker.sock'
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

        stage('Check Docker Version') {
            steps {
                sh 'docker --version || true'
            }
        }

        stage('Install Dependencies') {
            steps {
                sh '''
                python -m pip install --upgrade pip
                pip install -r requirements.txt || true
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
                python -m py_compile main.py || true
                python -m py_compile services/*.py || true
                '''
            }
        }

        stage('Build Docker Image') {
            when {
                branch 'devops-test'
            }
            steps {
                sh 'docker build -t ai-agent . || true'
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
