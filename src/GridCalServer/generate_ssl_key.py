# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime
import socket
import ipaddress


def get_my_ip():
    """Returns the IP address of the machine running the FastAPI server."""
    try:
        # Connect to an external server (Google's DNS) to determine our outward-facing IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"  # Fallback to localhost if detection fails
    return ip


def generate_ssl_certificate(ip: str | None = None, domain: str | None = None,
                             key_file_name="key.pem", cert_file_name="cert.pem"):
    """
    Generates a new SSL certificate and saves it to a file
    :param ip: IP address of the server (optional)
    :param domain: Domain name of the server (optional)
    :param key_file_name: name of the key file
    :param cert_file_name: name of the certificate file
    """

    subjects_list = [x509.DNSName(u"localhost")]

    if ip is not None:
        subjects_list.append(x509.IPAddress(ipaddress.ip_address(ip)))

    if domain is not None:
        subjects_list.append(x509.DNSName(domain))

    # Generate a private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    # Write the private key to a file
    with open(key_file_name, "wb") as key_file:
        key_file.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Define certificate subject and issuer details
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"ES"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Barcelona"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Barcelona"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"eRoots Analytics"),
        x509.NameAttribute(NameOID.COMMON_NAME, ip),
    ])

    # Build the certificate
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.UTC)
    ).not_valid_after(
        # Certificate is valid for 365 days
        datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName(subjects_list),
        critical=False,
    ).sign(private_key, hashes.SHA256(), default_backend())

    # Write the certificate to a file
    with open(cert_file_name, "wb") as cert_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"SSL certificate and key have been generated: cert={cert_file_name}, key={key_file_name}")


if __name__ == "__main__":
    generate_ssl_certificate(ip="127.0.0.1", key_file_name="key.pem")
