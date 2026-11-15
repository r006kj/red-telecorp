from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.client import Users, User
from diagrams.aws.iot import IotSensor
from diagrams.aws.integration import Eventbridge, SQS, StepFunctions, SNS
from diagrams.aws.compute import Lambda
from diagrams.aws.network import APIGateway
from diagrams.aws.integration import EventbridgeScheduler
from diagrams.aws.storage import S3
from diagrams.aws.mobile import Amplify
from diagrams.aws.security import Cognito, SecretsManager
from diagrams.aws.database import Dynamodb, DynamodbStreams
from diagrams.aws.engagement import SES
from diagrams.aws.management import Cloudwatch
from diagrams.gcp.compute import Run
from diagrams.gcp.ml import VertexAI
from diagrams.gcp.analytics import PubSub, BigQuery, Looker

graph_attr = {"fontsize": "26", "pad": "0.6", "nodesep": "0.6", "ranksep": "1.0", "splines": "spline"}
node_attr = {"fontsize": "13"}
red = {}

with Diagram("Red TeleCorp - Arquitectura serverless multinube (AWS + GCP)",
             filename="arquitectura", outformat=["png"],
             show=False, direction="LR", graph_attr=graph_attr, node_attr=node_attr):

    antenas = IotSensor("Antenas\n(GB/min)")
    usuarios = Users("Usuarios\n(web / móvil)")
    operador = User("Operadores")

    with Cluster("AWS"):
        with Cluster("Flujo de antenas"):
            sched = EventbridgeScheduler("EventBridge\nregla cada 1 min")
            sim = Lambda("Lambda\nsimular")
            eb = Eventbridge("EventBridge\n(ingesta métricas)")
            l_proc = Lambda("Lambda\nprocesar")
            q_dat = SQS("SQS\ncola_datos")
            dlq1 = SQS("DLQ\ncola_datos_dlq")
            l_clas = Lambda("Lambda clasificar\n0 = inhabilitada\n<60 = caída · >129 = saturada")

        with Cluster("Portal de usuarios"):
            web = Amplify("Amplify Hosting\n(portal y panel)")
            cognito = Cognito("Cognito\n(operadores)")
            api = APIGateway("API Gateway\n(REST)")
            l_rec = Lambda("Lambda\ncrearReporte")
            q_rep = SQS("SQS\ncola_reportes")
            dlq2 = SQS("DLQ\ncola_reportes_dlq")
            l_ext = Lambda("Lambda\nextraerDatos")
            l_corr = Lambda("Lambda correlacionar\n≥10 usuarios / zona / 24 h")

        secrets = SecretsManager("Secrets Manager\n(dev-secreto_gcp)")

        with Cluster("Datos (alta disponibilidad)"):
            ddb = Dynamodb("DynamoDB + PITR\nt_reportes · t_incidentes ·\nt_historial · t_zonas ...")
            streams = DynamodbStreams("DynamoDB\nStreams")

        with Cluster("Orquestación (Step Functions)"):
            sf_col = StepFunctions("Incidente colectivo\nverificar antenas → prioridad →\nnotificar → esperar operador\n→ restablecido")
            sf_rec = StepFunctions("Recurrencia\n≥3 fallas / 7 días")

        with Cluster("Notificación"):
            sns = SNS("SNS\n(SMS)")
            ses = SES("SES\n(correo)")
            ws = APIGateway("API Gateway\nWebSocket (panel)")

        l_exp = Lambda("Lambda\nexportar")
        s3 = S3("S3 versionado\n(respaldo crudo)")

        cw = Cloudwatch("CloudWatch\n(monitoreo y logs)")

    with Cluster("Google Cloud"):
        with Cluster("IA"):
            run = Run("Cloud Run function\nclasificar reporte")
            gemini = VertexAI("Vertex AI\n(Gemini)")
        with Cluster("Analítica histórica"):
            pubsub = PubSub("Pub/Sub\n(suscripción BigQuery)")
            bq = BigQuery("BigQuery\nincidentes y métricas")
            looker = Looker("Looker Studio\nzonas · antenas · tipos ·\nduración · usuarios")

    # Antenas
    sched >> sim >> Edge(label="simula") >> antenas >> eb >> l_proc >> q_dat >> l_clas
    q_dat >> Edge(style="dashed") >> dlq1
    l_clas >> ddb
    l_clas >> Edge(label="anomalía") >> sf_col
    l_clas >> sf_rec

    # Usuarios
    usuarios >> web >> api
    cognito - Edge(style="dashed") - api
    api >> l_rec >> q_rep >> l_ext
    q_rep >> Edge(style="dashed") >> dlq2
    l_ext >> Edge(label="tipo de problema") >> run >> gemini
    secrets >> Edge(style="dashed") >> l_ext
    l_ext >> ddb
    l_ext >> l_corr
    l_corr << Edge(label="cuenta usuarios") >> ddb
    l_corr >> Edge(label="dispara") >> sf_col

    # Orquestación
    sf_col >> ddb
    sf_rec >> ddb
    sf_col >> ses
    sf_col >> sns
    sf_col >> ws
    sf_rec >> ws
    ws >> operador
    operador >> Edge(style="dashed", label="panel") >> web

    # Analítica
    ddb >> streams >> l_exp >> s3
    l_exp >> Edge(label="eventos", **red) >> pubsub >> Edge(**red) >> bq >> Edge(**red) >> looker
    secrets >> Edge(style="dashed", **red) >> l_exp
    looker >> Edge(style="dashed") >> operador
