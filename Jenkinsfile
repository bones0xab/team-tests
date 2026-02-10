pipeline {
    agent any

    environment {
        PYTHON_VERSION = '3.11'
    }

    stages {


        stage('Install Dependencies') {
            steps {
                sh '''
                python -m pip install --upgrade pip
                pip install -r requirements.txt
                pip install pytest flake8 black
                '''
            }
        }

        stage('Lint') {
            steps {
                sh 'flake8 .'
            }
        }

        stage('Tests') {
            steps {
                sh 'pytest'
            }
        }

        stage('Validate Code') {
            steps {
                sh '''
                python -m py_compile main.py
                python -m py_compile services/Auth.py
                python -m py_compile services/Fetch.py
                python -m py_compile services/Normalisation.py
                '''
            }
        }

        stage('Run Dashboard') {
            steps {
                sh 'streamlit run main.py --server.headless true &'

            }
        }
    }
}
