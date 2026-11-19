import os
import datetime
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def generate_tls_bundle(cert_dir: str = "/certs"):
    os.makedirs(cert_dir, exist_ok=True)
    ca_crt_path = os.path.join(cert_dir, "ca.crt")
    ca_key_path = os.path.join(cert_dir, "ca.key")
    server_pem_path = os.path.join(cert_dir, "server.pem")
    client_pem_path = os.path.join(cert_dir, "client.pem")

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Generate Root CA key & self-signed certificate
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = ca_issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NoSQL Lab 12 Security"),
        x509.NameAttribute(NameOID.COMMON_NAME, "MongoDB-CA"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    with open(ca_key_path, "wb") as f:
        f.write(ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    with open(ca_crt_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))

    # 2. Generate Server key & CA-signed certificate (SAN: localhost, mongo12, 127.0.0.1)
    srv_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    srv_subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NoSQL Lab 12 Security"),
        x509.NameAttribute(NameOID.COMMON_NAME, "mongo12"),
    ])
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.DNSName("mongo12"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ])
    srv_cert = (
        x509.CertificateBuilder()
        .subject_name(srv_subject)
        .issuer_name(ca_cert.subject)
        .public_key(srv_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(san, critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    with open(server_pem_path, "wb") as f:
        f.write(srv_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
        f.write(srv_cert.public_bytes(serialization.Encoding.PEM))

    # 3. Generate Client key & CA-signed certificate for mutual TLS / PyMongo
    cli_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cli_subject = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NoSQL Lab 12 Security"),
        x509.NameAttribute(NameOID.COMMON_NAME, "pymongo-client"),
    ])
    cli_cert = (
        x509.CertificateBuilder()
        .subject_name(cli_subject)
        .issuer_name(ca_cert.subject)
        .public_key(cli_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(ca_key, hashes.SHA256())
    )
    with open(client_pem_path, "wb") as f:
        f.write(cli_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
        f.write(cli_cert.public_bytes(serialization.Encoding.PEM))

    return {
        "ca_crt": ca_crt_path,
        "server_pem": server_pem_path,
        "client_pem": client_pem_path,
        "ca_subject": ca_cert.subject.rfc4514_string(),
        "srv_subject": srv_cert.subject.rfc4514_string(),
        "cli_subject": cli_cert.subject.rfc4514_string(),
        "srv_fingerprint": srv_cert.fingerprint(hashes.SHA256()).hex()[:24],
    }

if __name__ == "__main__":
    info = generate_tls_bundle(os.getenv("CERT_DIR", "/certs"))
    print(f"[CERTS GENERATED] CA={info['ca_subject']} | Server={info['srv_subject']} | Client={info['cli_subject']}")