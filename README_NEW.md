# 🏦 NeuroBank FastAPI Toolkit

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.6-009639.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![AWS Serverless](https://img.shields.io/badge/AWS-Serverless-FF9900.svg?style=flat&logo=amazon-aws&logoColor=white)](https://aws.amazon.com/serverless/)
[![License: Source-Available](https://img.shields.io/badge/License-Source--Available-blue.svg)](LICENSE)

**Enterprise-grade FastAPI toolkit para operaciones bancarias con infraestructura serverless en AWS**

## 🚀 **Características Principales**

### 🏗️ **Infrastructure as Code**
- ✅ **AWS SAM Stack**: Lambda + API Gateway + CloudWatch + X-Ray
- ✅ **Containerización**: Docker multi-stage con optimizaciones de seguridad
- ✅ **Auto-scaling**: Escalado automático con límites configurables
- ✅ **Rate Limiting**: Protección contra abuso (10K req/month, 50 req/seg burst)

### 🔐 **Seguridad Enterprise**
- ✅ **AWS OIDC**: Autenticación sin credenciales de larga duración
- ✅ **API Key Authentication**: Sistema de autenticación robusto
- ✅ **Security Scanning**: Bandit (SAST) + Safety (vulnerabilidades)
- ✅ **Container Security**: Usuario no-root, superficie de ataque mínima

### ⚡ **DevOps Excellence**
- ✅ **CI/CD Automatizado**: GitHub Actions con control manual de deployments
- ✅ **Multi-Environment**: Development/Staging/Production separados
- ✅ **Emergency Pipeline**: Hotfix deployment para issues críticos
- ✅ **Comprehensive Testing**: pytest con coverage completo

### 📊 **Observabilidad**
- ✅ **CloudWatch Dashboard**: Métricas en tiempo real (15+ indicadores)
- ✅ **Structured Logging**: Formato JSON con request tracing
- ✅ **X-Ray Tracing**: Análisis de performance distribuido
- ✅ **Cost Monitoring**: Optimización automática de costos AWS

## 📋 **Tabla de Contenidos**

- [🚀 Instalación y Setup](#-instalación-y-setup)
- [🏃‍♂️ Quick Start](#️-quick-start)
- [🛠️ Desarrollo Local](#️-desarrollo-local)
- [☁️ Deployment en AWS](#️-deployment-en-aws)
- [📚 Documentación API](#-documentación-api)
- [🔧 Configuración](#-configuración)
- [🧪 Testing](#-testing)
- [📈 Monitoreo](#-monitoreo)
- [🤝 Contribución](#-contribución)

## 🚀 **Instalación y Setup**

### **Prerequisitos**
```bash
# Versiones requeridas
Python >= 3.11
Docker >= 20.10
AWS CLI >= 2.0
AWS SAM CLI >= 1.100
```

### **Clone del repositorio**
```bash
git clone https://github.com/Neiland85/clarity-critical-ops-spanner-lab.git
cd clarity-critical-ops-spanner-lab
```

### **Configuración del entorno**
```bash
# Crear entorno virtual
python -m venv neurobank-env
source neurobank-env/bin/activate  # Linux/macOS
# neurobank-env\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## 🏃‍♂️ **Quick Start**

### **1. Desarrollo local**
```bash
# Ejecutar servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Acceder a la documentación
open http://localhost:8000/docs
```

### **2. Con Docker**
```bash
# Build y run
docker build -t neurobank-api .
docker run -p 8000:8000 neurobank-api
```

### **3. Con Docker Compose**
```bash
# Desarrollo completo con hot-reload
docker-compose up --build
```

## 🛠️ **Desarrollo Local**

### **Estructura del proyecto**
```
clarity-critical-ops-spanner-lab/
├── app/                          # Código fuente principal
│   ├── routers/                  # Endpoints organizados por módulo
│   │   └── operator.py          # Operaciones bancarias
│   ├── services/                 # Lógica de negocio
│   │   ├── order_service.py     # Gestión de órdenes
│   │   └── invoice_service.py   # Generación de facturas
│   ├── auth/                     # Autenticación y seguridad
│   │   └── dependencies.py      # Dependencias de auth
│   ├── utils/                    # Utilidades
│   │   └── logging.py           # Configuración de logging
│   └── main.py                  # Aplicación principal
├── tests/                        # Suite de tests
├── .github/workflows/           # CI/CD pipelines
├── template.yaml               # AWS SAM template
├── Dockerfile                  # Container configuration
└── requirements.txt           # Python dependencies
```

### **Comandos de desarrollo**
```bash
# Ejecutar tests
pytest

# Tests con coverage
pytest --cov=app --cov-report=html

# Linting y formateo
bandit -r app/
safety check

# Hot-reload development
uvicorn app.main:app --reload
```

## ☁️ **Deployment en AWS**

### **1. Configuración de OIDC (One-time setup)**
```bash
# Seguir la guía completa en AWS_OIDC_SETUP.md
# Configurar role: GitHubActionsOIDCRole
# Account ID: 120242956739
```

### **2. Deployment manual via GitHub Actions**
1. Ir a **Actions** tab en GitHub
2. Seleccionar "CI/CD Pipeline"
3. Click "Run workflow"
4. Seleccionar:
   - `deploy_to_aws`: `true`
   - `environment`: `production`
5. Click "Run workflow"

### **3. Verificación post-deployment**
```bash
# Obtener URL del API Gateway
aws cloudformation describe-stacks \
  --stack-name neurobank-api \
  --query 'Stacks[0].Outputs'

# Test health check
curl https://YOUR-API-ID.execute-api.eu-west-1.amazonaws.com/Prod/health
```

## 📚 **Documentación API**

### **Endpoints principales**

| Endpoint | Método | Descripción | Autenticación |
|----------|---------|-------------|---------------|
| `/` | GET | Welcome + navegación | No |
| `/health` | GET | Health check detallado | No |
| `/docs` | GET | Swagger UI interactivo | No |
| `/operator/order_status/{id}` | GET | Estado de orden bancaria | API Key |
| `/operator/generate_invoice` | POST | Generar factura | API Key |

### **Autenticación**
```bash
# Header requerido para endpoints protegidos
curl -H "X-API-Key: YOUR-API-KEY" \
     https://api.neurobank.com/operator/order_status/ORD-2025-001234
```

### **Ejemplos de uso**

#### **Consultar estado de orden**
```bash
curl -X GET \
  -H "X-API-Key: your-api-key-here" \
  "https://api.neurobank.com/operator/order_status/ORD-2025-001234"

# Response
{
  "order_id": "ORD-2025-001234",
  "status": "processing",
  "carrier": "VISA_NETWORK",
  "eta": "2025-07-20T16:30:00Z"
}
```

#### **Generar factura**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"order_id": "ORD-2025-001234"}' \
  "https://api.neurobank.com/operator/generate_invoice"

# Response
{
  "invoice_id": "INV-2025-789012",
  "order_id": "ORD-2025-001234", 
  "amount": 1250.75,
  "currency": "EUR",
  "issued_at": "2025-07-20T15:45:30Z"
}
```

## 🔧 **Configuración**

### **Variables de entorno**
```bash
# Desarrollo local (.env)
ENVIRONMENT=development
LOG_LEVEL=INFO
API_KEY=your-development-key

# AWS Lambda (automático via SAM)
ENVIRONMENT=production
AWS_REGION=eu-west-1
```

### **GitHub Secrets requeridos**
```bash
# Configurar en: Settings > Secrets and variables > Actions
AWS_ACCOUNT_ID=120242956739    # Tu AWS Account ID
API_KEY=your-production-key    # Opcional (se genera automáticamente)
```

## 🧪 **Testing**

### **Ejecutar suite completa**
```bash
# Tests unitarios
pytest

# Con coverage detallado  
pytest --cov=app --cov-report=html --cov-report=term-missing

# Tests de endpoints específicos
pytest tests/test_endpoints.py::test_health_endpoint -v
```

### **Tests de integración**
```bash
# Test completo con Docker
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Security testing
bandit -r app/ -f json -o security-report.json
safety check --json --output safety-report.json
```

## 📈 **Monitoreo**

### **CloudWatch Dashboard**
- **Lambda Metrics**: Duration, Errors, Invocations, Throttles
- **API Gateway**: Request count, Latency, 4xx/5xx errors  
- **Custom Metrics**: Business KPIs y performance indicators

### **Logging estructurado**
```json
{
  "timestamp": "2025-07-20T15:45:30.123456Z",
  "level": "INFO",
  "service": "neurobank-api",
  "request_id": "abc123-def456",
  "endpoint": "/operator/order_status/ORD-2025-001234",
  "response_time_ms": 125,
  "status_code": 200
}
```

### **Alertas automáticas**
- Error rate > 1%
- Average latency > 5s
- Lambda throttling detected
- Cost threshold exceeded

## 🤝 **Contribución**

### **Git Workflow**
```bash
# Crear feature branch
git checkout develop
git pull origin develop
git checkout -b feature/nueva-funcionalidad

# Desarrollo y commits
git add .
git commit -m "feat: descripción de la funcionalidad"

# Push y Pull Request
git push origin feature/nueva-funcionalidad
# Crear PR desde GitHub UI: feature/nueva-funcionalidad → develop
```

### **Standards de código**
- **Python**: PEP 8, type hints, docstrings
- **Commits**: Conventional Commits format
- **Testing**: Min 80% coverage, unit + integration tests
- **Security**: Bandit scan clean, Safety check passed

### **Review checklist**
- [ ] Tests passing (4/4)
- [ ] Security scans clean
- [ ] Documentation updated
- [ ] API examples working
- [ ] Performance impact assessed

## 📄 **Licencia**

La baseline actual está sujeta a la **Clarity Structures Commercial
Source-Available License v1.1**; consulta [LICENSE](LICENSE).

Las copias históricas que hubieran sido distribuidas válidamente bajo MIT
conservan únicamente los derechos correspondientes a esas copias específicas.
Consulta también [NOTICE.md](NOTICE.md).

## 🆘 **Soporte**

- **Issues**: [GitHub Issues](https://github.com/Neiland85/clarity-critical-ops-spanner-lab/issues)
- **Documentation**: [Wiki](https://github.com/Neiland85/clarity-critical-ops-spanner-lab/wiki)
- **AWS Setup**: [AWS_OIDC_SETUP.md](AWS_OIDC_SETUP.md)

---

**🎯 NeuroBank FastAPI Toolkit - Powering modern banking infrastructure with serverless excellence! 🚀**
