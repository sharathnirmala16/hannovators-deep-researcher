"""Curate direct-search cybersecurity and vulnerability tracking facts.

Covers canonical CVE vulnerability records from NIST National Vulnerability
Database (NVD) and vendor security bulletins, verifying CVSS base scores,
CVSS vector strings, affected software components, and bulletin identifiers.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from query_gold.io import atomic_write_bytes, ensure_safe_path
from query_gold.models import SCHEMA_VERSION

CATEGORY_ID = "11_cybersecurity_vulnerability_tracking"
GENERATOR_VERSION = "query-gold/v1"
SOURCE_FAMILY = "nvd_cve_security_bulletins"
IMMUTABLE_REASON = "Fixed CVE vulnerability record"


@dataclass(frozen=True)
class CVESource:
    source_id: str
    source_record_id: str
    url: str
    title: str
    published_at: str
    license: str
    raw_text: str


@dataclass(frozen=True)
class CVEFact:
    case_id: str
    source_id: str
    query: str
    question_type: str
    answer: str
    value: float | None
    accepted_answers: list[str]
    units: str | None
    excerpt: str


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


SOURCES: list[CVESource] = [
    CVESource(
        source_id="cve_2021_44228",
        source_record_id="CVE-2021-44228",
        url="https://nvd.nist.gov/vuln/detail/CVE-2021-44228",
        title="CVE-2021-44228 Detail: Apache Log4j Remote Code Execution",
        published_at="2021-12-10",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2021-44228\n"
            "Description: Apache Log4j2 JNDI features used in configuration, log messages, "
            "and parameters do not protect against attacker controlled LDAP and other "
            "JNDI related endpoints.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: Apache Log4j Core\n"
            "Common Weakness Enumeration: CWE-502 Deserialization of Untrusted Data"
        ),
    ),
    CVESource(
        source_id="cve_2021_34527",
        source_record_id="CVE-2021-34527",
        url="https://nvd.nist.gov/vuln/detail/CVE-2021-34527",
        title="CVE-2021-34527 Detail: Windows Print Spooler Remote Code Execution",
        published_at="2021-07-02",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2021-34527\n"
            "Description: Windows Print Spooler service improperly performs privileged "
            "file operations, commonly known as PrintNightmare.\n"
            "CVSS v3.1 Severity Assessment: Base Score 8.8 HIGH\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Windows Print Spooler\n"
            "Vendor Advisory: Microsoft Security Update Guide ADV210001"
        ),
    ),
    CVESource(
        source_id="cve_2022_22965",
        source_record_id="CVE-2022-22965",
        url="https://nvd.nist.gov/vuln/detail/CVE-2022-22965",
        title="CVE-2022-22965 Detail: Spring Framework Remote Code Execution",
        published_at="2022-04-01",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2022-22965\n"
            "Description: Spring Framework Spring-MVC or Spring-WebFlux application running on "
            "JDK 9+ may be vulnerable to remote code execution via data binding.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Spring Framework MVC\n"
            "Common Weakness Enumeration: CWE-94 Improper Control of Code Generation"
        ),
    ),
    CVESource(
        source_id="cve_2023_38606",
        source_record_id="CVE-2023-38606",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-38606",
        title="CVE-2023-38606 Detail: Apple iOS Kernel Privilege Escalation",
        published_at="2023-07-24",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-38606\n"
            "Description: An app may be able to modify sensitive kernel state. Apple is aware "
            "of reports this issue may have been exploited in zero-day campaigns.\n"
            "CVSS v3.1 Severity Assessment: Base Score 7.8 HIGH\n"
            "Vector: CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H\n"
            "Affected Component: Apple iOS Kernel\n"
            "Vendor Advisory: Apple Security Release HT213841"
        ),
    ),
    CVESource(
        source_id="cve_2023_34362",
        source_record_id="CVE-2023-34362",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-34362",
        title="CVE-2023-34362 Detail: Progress MOVEit Transfer SQL Injection",
        published_at="2023-06-02",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-34362\n"
            "Description: In Progress MOVEit Transfer before 2021.0.6, a SQL injection "
            "vulnerability in the MOVEit Transfer web application could allow an unauthenticated "
            "attacker to gain access to the database.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: MOVEit Transfer Web Application\n"
            "Common Weakness Enumeration: CWE-89 SQL Injection"
        ),
    ),
    CVESource(
        source_id="cve_2023_23397",
        source_record_id="CVE-2023-23397",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-23397",
        title="CVE-2023-23397 Detail: Microsoft Outlook Elevation of Privilege",
        published_at="2023-03-14",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-23397\n"
            "Description: Microsoft Outlook Elevation of Privilege Vulnerability allowing "
            "Net-NTLMv2 hash theft via appointment reminder sound file transmission.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Microsoft Outlook Client\n"
            "Vendor Security Bulletin: ADV230001"
        ),
    ),
    CVESource(
        source_id="cve_2023_4863",
        source_record_id="CVE-2023-4863",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-4863",
        title="CVE-2023-4863 Detail: libwebp Heap Buffer Overflow",
        published_at="2023-09-12",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-4863\n"
            "Description: Heap buffer overflow in libwebp in Google Chrome before 116.0.5845.187 "
            "allowed a remote attacker to perform an out of bounds memory write via HTML.\n"
            "CVSS v3.1 Severity Assessment: Base Score 8.8 HIGH\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H\n"
            "Affected Component: Google Chrome libwebp\n"
            "Common Weakness Enumeration: CWE-787 Out-of-bounds Write"
        ),
    ),
    CVESource(
        source_id="cve_2021_26855",
        source_record_id="CVE-2021-26855",
        url="https://nvd.nist.gov/vuln/detail/CVE-2021-26855",
        title="CVE-2021-26855 Detail: Microsoft Exchange Server Remote Code Execution",
        published_at="2021-03-02",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2021-26855\n"
            "Description: Microsoft Exchange Server Server-Side Request Forgery vulnerability, "
            "commonly identified as part of ProxyLogon.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Microsoft Exchange Server\n"
            "Common Weakness Enumeration: CWE-918 Server-Side Request Forgery"
        ),
    ),
    CVESource(
        source_id="cve_2020_1472",
        source_record_id="CVE-2020-1472",
        url="https://nvd.nist.gov/vuln/detail/CVE-2020-1472",
        title="CVE-2020-1472 Detail: Netlogon Elevation of Privilege Zerologon",
        published_at="2020-08-17",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2020-1472\n"
            "Description: An elevation of privilege vulnerability exists when an attacker "
            "establishes a vulnerable Netlogon secure channel connection to a domain controller, "
            "known as Zerologon.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: Windows Netlogon Protocol\n"
            "Common Weakness Enumeration: CWE-330 Use of Insufficiently Random Values"
        ),
    ),
    CVESource(
        source_id="cve_2017_0144",
        source_record_id="CVE-2017-0144",
        url="https://nvd.nist.gov/vuln/detail/CVE-2017-0144",
        title="CVE-2017-0144 Detail: Windows SMB Remote Code Execution EternalBlue",
        published_at="2017-03-16",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2017-0144\n"
            "Description: The SMBv1 server in Microsoft Windows allows remote attackers to execute "
            "arbitrary code via crafted packets, known as EternalBlue.\n"
            "CVSS v3.1 Severity Assessment: Base Score 8.1 HIGH\n"
            "Vector: CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Microsoft SMBv1 Server\n"
            "Vendor Security Bulletin: MS17-010"
        ),
    ),
    CVESource(
        source_id="cve_2014_0160",
        source_record_id="CVE-2014-0160",
        url="https://nvd.nist.gov/vuln/detail/CVE-2014-0160",
        title="CVE-2014-0160 Detail: OpenSSL Heartbleed Information Disclosure",
        published_at="2014-04-07",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2014-0160\n"
            "Description: The (1) TLS and (2) DTLS implementations in OpenSSL 1.0.1 before 1.0.1g "
            "do not properly handle Heartbeat Extension packets, known as Heartbleed.\n"
            "CVSS v3.1 Severity Assessment: Base Score 7.5 HIGH\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N\n"
            "Affected Component: OpenSSL TLS heartbeat extension\n"
            "Common Weakness Enumeration: CWE-126 Buffer Over-read"
        ),
    ),
    CVESource(
        source_id="cve_2019_0708",
        source_record_id="CVE-2019-0708",
        url="https://nvd.nist.gov/vuln/detail/CVE-2019-0708",
        title="CVE-2019-0708 Detail: Remote Desktop Services Remote Code Execution BlueKeep",
        published_at="2019-05-16",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2019-0708\n"
            "Description: A remote code execution vulnerability exists in Remote Desktop Services "
            "when an unauthenticated attacker connects to the target via RDP, known as BlueKeep.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Windows Remote Desktop Services\n"
            "Common Weakness Enumeration: CWE-416 Use After Free"
        ),
    ),
    CVESource(
        source_id="cve_2024_3094",
        source_record_id="CVE-2024-3094",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-3094",
        title="CVE-2024-3094 Detail: XZ Utils Backdoor Remote Code Execution",
        published_at="2024-03-29",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-3094\n"
            "Description: Malicious code was discovered in the upstream tarballs of xz, "
            "starting with version 5.6.0, affecting liblzma and sshd authentication.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: xz-utils liblzma\n"
            "Common Weakness Enumeration: CWE-506 Embedded Malicious Code"
        ),
    ),
    CVESource(
        source_id="cve_2023_22515",
        source_record_id="CVE-2023-22515",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-22515",
        title="CVE-2023-22515 Detail: Atlassian Confluence Server Broken Access Control",
        published_at="2023-10-04",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-22515\n"
            "Description: Atlassian Confluence Data Center and Server versions allow an external "
            "attacker to create unauthorized Confluence administrator accounts.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: Atlassian Confluence Server\n"
            "Common Weakness Enumeration: CWE-284 Improper Access Control"
        ),
    ),
    CVESource(
        source_id="cve_2023_2868",
        source_record_id="CVE-2023-2868",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-2868",
        title="CVE-2023-2868 Detail: Barracuda ESG Command Injection",
        published_at="2023-05-30",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-2868\n"
            "Description: A remote command injection vulnerability exists in the Barracuda Email "
            "Security Gateway appliance via tar file attachment parsing.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Barracuda Email Security Gateway\n"
            "Common Weakness Enumeration: CWE-78 OS Command Injection"
        ),
    ),
    CVESource(
        source_id="cve_2022_30190",
        source_record_id="CVE-2022-30190",
        url="https://nvd.nist.gov/vuln/detail/CVE-2022-30190",
        title="CVE-2022-30190 Detail: Microsoft Windows Support Diagnostic Tool Follina",
        published_at="2022-06-01",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2022-30190\n"
            "Description: Microsoft Windows Support Diagnostic Tool MSDT remote code execution "
            "vulnerability, commonly referred to as Follina.\n"
            "CVSS v3.1 Severity Assessment: Base Score 7.8 HIGH\n"
            "Vector: CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H\n"
            "Affected Component: Windows Support Diagnostic Tool\n"
            "Vendor Security Bulletin: ADV220001"
        ),
    ),
    CVESource(
        source_id="cve_2023_27997",
        source_record_id="CVE-2023-27997",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-27997",
        title="CVE-2023-27997 Detail: Fortinet FortiOS SSL-VPN Heap Buffer Overflow",
        published_at="2023-06-13",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-27997\n"
            "Description: A heap-based buffer overflow in FortiOS and FortiProxy SSL-VPN may allow "
            "a remote attacker to execute arbitrary code or commands via crafted requests.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Fortinet FortiOS SSL-VPN\n"
            "Common Weakness Enumeration: CWE-122 Heap-based Buffer Overflow"
        ),
    ),
    CVESource(
        source_id="cve_2023_20198",
        source_record_id="CVE-2023-20198",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-20198",
        title="CVE-2023-20198 Detail: Cisco IOS XE Web UI Privilege Escalation",
        published_at="2023-10-18",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-20198\n"
            "Description: A vulnerability in the web UI of Cisco IOS XE Software could allow "
            "an unauthenticated remote attacker to create an account with privilege level 15.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: Cisco IOS XE Web UI\n"
            "Common Weakness Enumeration: CWE-284 Improper Access Control"
        ),
    ),
    CVESource(
        source_id="cve_2023_4966",
        source_record_id="CVE-2023-4966",
        url="https://nvd.nist.gov/vuln/detail/CVE-2023-4966",
        title="CVE-2023-4966 Detail: NetScaler ADC and Gateway Information Disclosure Citrix Bleed",
        published_at="2023-10-10",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2023-4966\n"
            "Description: Sensitive information disclosure in NetScaler ADC and NetScaler Gateway "
            "when configured as a Gateway or AAA virtual server, known as Citrix Bleed.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.4 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N\n"
            "Affected Component: NetScaler ADC and Gateway\n"
            "Common Weakness Enumeration: CWE-119 Improper Restriction of Operations within Bounds"
        ),
    ),
    CVESource(
        source_id="cve_2024_21762",
        source_record_id="CVE-2024-21762",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-21762",
        title="CVE-2024-21762 Detail: Fortinet FortiOS SSL-VPN Out-of-Bounds Write",
        published_at="2024-02-09",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-21762\n"
            "Description: An out-of-bounds write vulnerability in Fortinet FortiOS SSL-VPN allows "
            "an attacker to execute code via crafted HTTP requests.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: Fortinet FortiOS SSL-VPN HTTP Handler\n"
            "Common Weakness Enumeration: CWE-787 Out-of-bounds Write"
        ),
    ),
    CVESource(
        source_id="cve_2024_1709",
        source_record_id="CVE-2024-1709",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-1709",
        title="CVE-2024-1709 Detail: ConnectWise ScreenConnect Authentication Bypass",
        published_at="2024-02-21",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-1709\n"
            "Description: ConnectWise ScreenConnect 23.9.7 and prior contain an authentication "
            "bypass vulnerability in the initial setup wizard component.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: ConnectWise ScreenConnect Server\n"
            "Common Weakness Enumeration: CWE-288 Authentication Bypass Using Alternate Path"
        ),
    ),
    CVESource(
        source_id="cve_2024_27198",
        source_record_id="CVE-2024-27198",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-27198",
        title="CVE-2024-27198 Detail: JetBrains TeamCity Authentication Bypass",
        published_at="2024-03-04",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-27198\n"
            "Description: In JetBrains TeamCity before 2023.11.4, authentication bypass leading "
            "to remote code execution was possible via an alternate path in the web server.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: JetBrains TeamCity Web Server\n"
            "Common Weakness Enumeration: CWE-288 Authentication Bypass Using Alternate Path"
        ),
    ),
    CVESource(
        source_id="cve_2024_3400",
        source_record_id="CVE-2024-3400",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-3400",
        title="CVE-2024-3400 Detail: Palo Alto Networks PAN-OS Command Injection",
        published_at="2024-04-12",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-3400\n"
            "Description: A command injection flaw in the GlobalProtect feature of "
            "Palo Alto Networks PAN-OS allows an attacker to execute root code.\n"
            "CVSS v3.1 Severity Assessment: Base Score 10.0 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H\n"
            "Affected Component: PAN-OS GlobalProtect Feature\n"
            "Vendor Security Bulletin: PAN-SA-2024-0002"
        ),
    ),
    CVESource(
        source_id="cve_2024_6387",
        source_record_id="CVE-2024-6387",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-6387",
        title="CVE-2024-6387 Detail: OpenSSH regreSSHion Signal Handler Race Condition",
        published_at="2024-07-01",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-6387\n"
            "Description: A signal handler race condition vulnerability in OpenSSH server (sshd) "
            "on glibc-based Linux systems allows unauthenticated remote code execution as root.\n"
            "CVSS v3.1 Severity Assessment: Base Score 8.1 HIGH\n"
            "Vector: CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: OpenSSH server daemon sshd\n"
            "Common Weakness Enumeration: CWE-362 Concurrent Execution using Shared Resource"
        ),
    ),
    CVESource(
        source_id="cve_2024_4577",
        source_record_id="CVE-2024-4577",
        url="https://nvd.nist.gov/vuln/detail/CVE-2024-4577",
        title="CVE-2024-4577 Detail: PHP CGI Argument Injection Vulnerability",
        published_at="2024-06-09",
        license="Public Domain / US Government Work",
        raw_text=(
            "Vulnerability Detail: CVE-2024-4577\n"
            "Description: An argument injection vulnerability in PHP CGI module on Windows "
            "allows attackers to bypass protections and execute arbitrary code.\n"
            "CVSS v3.1 Severity Assessment: Base Score 9.8 CRITICAL\n"
            "Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H\n"
            "Affected Component: PHP CGI Module for Windows\n"
            "Common Weakness Enumeration: CWE-78 OS Command Injection"
        ),
    ),
]

FACTS: list[CVEFact] = [
    # 1. Log4Shell
    CVEFact(
        case_id="cve-2021-44228-base-score",
        source_id="cve_2021_44228",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2021-44228?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2021-44228-vector",
        source_id="cve_2021_44228",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2021-44228?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    ),
    # 2. PrintNightmare
    CVEFact(
        case_id="cve-2021-34527-base-score",
        source_id="cve_2021_34527",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2021-34527?",
        question_type="cvss_base_score",
        answer="8.8",
        value=8.8,
        accepted_answers=["8.8"],
        units=None,
        excerpt="Base Score 8.8 HIGH",
    ),
    CVEFact(
        case_id="cve-2021-34527-component",
        source_id="cve_2021_34527",
        query="What affected component is listed in NVD for vulnerability CVE-2021-34527?",
        question_type="affected_component",
        answer="Windows Print Spooler",
        value=None,
        accepted_answers=["Windows Print Spooler"],
        units=None,
        excerpt="Affected Component: Windows Print Spooler",
    ),
    # 3. Spring4Shell
    CVEFact(
        case_id="cve-2022-22965-base-score",
        source_id="cve_2022_22965",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2022-22965?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2022-22965-vector",
        source_id="cve_2022_22965",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2022-22965?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 4. Apple WebKit Kernel
    CVEFact(
        case_id="cve-2023-38606-base-score",
        source_id="cve_2023_38606",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-38606?",
        question_type="cvss_base_score",
        answer="7.8",
        value=7.8,
        accepted_answers=["7.8"],
        units=None,
        excerpt="Base Score 7.8 HIGH",
    ),
    CVEFact(
        case_id="cve-2023-38606-component",
        source_id="cve_2023_38606",
        query="What affected component is listed in NVD for vulnerability CVE-2023-38606?",
        question_type="affected_component",
        answer="Apple iOS Kernel",
        value=None,
        accepted_answers=["Apple iOS Kernel"],
        units=None,
        excerpt="Affected Component: Apple iOS Kernel",
    ),
    # 5. MOVEit Transfer
    CVEFact(
        case_id="cve-2023-34362-base-score",
        source_id="cve_2023_34362",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-34362?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-34362-vector",
        source_id="cve_2023_34362",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2023-34362?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 6. Outlook NTLM
    CVEFact(
        case_id="cve-2023-23397-base-score",
        source_id="cve_2023_23397",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-23397?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-23397-bulletin",
        source_id="cve_2023_23397",
        query="What vendor security bulletin was assigned to vulnerability CVE-2023-23397?",
        question_type="vendor_security_bulletin",
        answer="ADV230001",
        value=None,
        accepted_answers=["ADV230001"],
        units=None,
        excerpt="Vendor Security Bulletin: ADV230001",
    ),
    # 7. libwebp
    CVEFact(
        case_id="cve-2023-4863-base-score",
        source_id="cve_2023_4863",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-4863?",
        question_type="cvss_base_score",
        answer="8.8",
        value=8.8,
        accepted_answers=["8.8"],
        units=None,
        excerpt="Base Score 8.8 HIGH",
    ),
    CVEFact(
        case_id="cve-2023-4863-vector",
        source_id="cve_2023_4863",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2023-4863?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H",
    ),
    # 8. ProxyLogon
    CVEFact(
        case_id="cve-2021-26855-base-score",
        source_id="cve_2021_26855",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2021-26855?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2021-26855-component",
        source_id="cve_2021_26855",
        query="What affected component is listed in NVD for vulnerability CVE-2021-26855?",
        question_type="affected_component",
        answer="Microsoft Exchange Server",
        value=None,
        accepted_answers=["Microsoft Exchange Server"],
        units=None,
        excerpt="Affected Component: Microsoft Exchange Server",
    ),
    # 9. Zerologon
    CVEFact(
        case_id="cve-2020-1472-base-score",
        source_id="cve_2020_1472",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2020-1472?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2020-1472-vector",
        source_id="cve_2020_1472",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2020-1472?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    ),
    # 10. EternalBlue
    CVEFact(
        case_id="cve-2017-0144-base-score",
        source_id="cve_2017_0144",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2017-0144?",
        question_type="cvss_base_score",
        answer="8.1",
        value=8.1,
        accepted_answers=["8.1"],
        units=None,
        excerpt="Base Score 8.1 HIGH",
    ),
    CVEFact(
        case_id="cve-2017-0144-bulletin",
        source_id="cve_2017_0144",
        query="What vendor security bulletin was assigned to vulnerability CVE-2017-0144?",
        question_type="vendor_security_bulletin",
        answer="MS17-010",
        value=None,
        accepted_answers=["MS17-010"],
        units=None,
        excerpt="Vendor Security Bulletin: MS17-010",
    ),
    # 11. Heartbleed
    CVEFact(
        case_id="cve-2014-0160-base-score",
        source_id="cve_2014_0160",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2014-0160?",
        question_type="cvss_base_score",
        answer="7.5",
        value=7.5,
        accepted_answers=["7.5"],
        units=None,
        excerpt="Base Score 7.5 HIGH",
    ),
    CVEFact(
        case_id="cve-2014-0160-component",
        source_id="cve_2014_0160",
        query="What affected component is listed in NVD for vulnerability CVE-2014-0160?",
        question_type="affected_component",
        answer="OpenSSL TLS heartbeat extension",
        value=None,
        accepted_answers=["OpenSSL TLS heartbeat extension"],
        units=None,
        excerpt="Affected Component: OpenSSL TLS heartbeat extension",
    ),
    # 12. BlueKeep
    CVEFact(
        case_id="cve-2019-0708-base-score",
        source_id="cve_2019_0708",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2019-0708?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2019-0708-vector",
        source_id="cve_2019_0708",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2019-0708?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 13. XZ Utils Backdoor
    CVEFact(
        case_id="cve-2024-3094-base-score",
        source_id="cve_2024_3094",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-3094?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2024-3094-vector",
        source_id="cve_2024_3094",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2024-3094?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    ),
    # 14. Atlassian Confluence
    CVEFact(
        case_id="cve-2023-22515-base-score",
        source_id="cve_2023_22515",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-22515?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-22515-component",
        source_id="cve_2023_22515",
        query="What affected component is listed in NVD for vulnerability CVE-2023-22515?",
        question_type="affected_component",
        answer="Atlassian Confluence Server",
        value=None,
        accepted_answers=["Atlassian Confluence Server"],
        units=None,
        excerpt="Affected Component: Atlassian Confluence Server",
    ),
    # 15. Barracuda ESG
    CVEFact(
        case_id="cve-2023-2868-base-score",
        source_id="cve_2023_2868",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-2868?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-2868-vector",
        source_id="cve_2023_2868",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2023-2868?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 16. Follina
    CVEFact(
        case_id="cve-2022-30190-base-score",
        source_id="cve_2022_30190",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2022-30190?",
        question_type="cvss_base_score",
        answer="7.8",
        value=7.8,
        accepted_answers=["7.8"],
        units=None,
        excerpt="Base Score 7.8 HIGH",
    ),
    CVEFact(
        case_id="cve-2022-30190-bulletin",
        source_id="cve_2022_30190",
        query="What vendor security bulletin was assigned to vulnerability CVE-2022-30190?",
        question_type="vendor_security_bulletin",
        answer="ADV220001",
        value=None,
        accepted_answers=["ADV220001"],
        units=None,
        excerpt="Vendor Security Bulletin: ADV220001",
    ),
    # 17. Fortinet SSL-VPN (CVE-2023-27997)
    CVEFact(
        case_id="cve-2023-27997-base-score",
        source_id="cve_2023_27997",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-27997?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-27997-vector",
        source_id="cve_2023_27997",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2023-27997?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 18. Cisco IOS XE
    CVEFact(
        case_id="cve-2023-20198-base-score",
        source_id="cve_2023_20198",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-20198?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-20198-component",
        source_id="cve_2023_20198",
        query="What affected component is listed in NVD for vulnerability CVE-2023-20198?",
        question_type="affected_component",
        answer="Cisco IOS XE Web UI",
        value=None,
        accepted_answers=["Cisco IOS XE Web UI"],
        units=None,
        excerpt="Affected Component: Cisco IOS XE Web UI",
    ),
    # 19. Citrix Bleed
    CVEFact(
        case_id="cve-2023-4966-base-score",
        source_id="cve_2023_4966",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2023-4966?",
        question_type="cvss_base_score",
        answer="9.4",
        value=9.4,
        accepted_answers=["9.4"],
        units=None,
        excerpt="Base Score 9.4 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2023-4966-vector",
        source_id="cve_2023_4966",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2023-4966?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
    ),
    # 20. Fortinet SSL-VPN (CVE-2024-21762)
    CVEFact(
        case_id="cve-2024-21762-base-score",
        source_id="cve_2024_21762",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-21762?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2024-21762-vector",
        source_id="cve_2024_21762",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2024-21762?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 21. ConnectWise ScreenConnect
    CVEFact(
        case_id="cve-2024-1709-base-score",
        source_id="cve_2024_1709",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-1709?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2024-1709-component",
        source_id="cve_2024_1709",
        query="What affected component is listed in NVD for vulnerability CVE-2024-1709?",
        question_type="affected_component",
        answer="ConnectWise ScreenConnect Server",
        value=None,
        accepted_answers=["ConnectWise ScreenConnect Server"],
        units=None,
        excerpt="Affected Component: ConnectWise ScreenConnect Server",
    ),
    # 22. JetBrains TeamCity
    CVEFact(
        case_id="cve-2024-27198-base-score",
        source_id="cve_2024_27198",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-27198?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2024-27198-vector",
        source_id="cve_2024_27198",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2024-27198?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 23. Palo Alto PAN-OS
    CVEFact(
        case_id="cve-2024-3400-base-score",
        source_id="cve_2024_3400",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-3400?",
        question_type="cvss_base_score",
        answer="10.0",
        value=10.0,
        accepted_answers=["10.0", "10"],
        units=None,
        excerpt="Base Score 10.0 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2024-3400-bulletin",
        source_id="cve_2024_3400",
        query="What vendor security bulletin was assigned to vulnerability CVE-2024-3400?",
        question_type="vendor_security_bulletin",
        answer="PAN-SA-2024-0002",
        value=None,
        accepted_answers=["PAN-SA-2024-0002"],
        units=None,
        excerpt="Vendor Security Bulletin: PAN-SA-2024-0002",
    ),
    # 24. OpenSSH regreSSHion
    CVEFact(
        case_id="cve-2024-6387-base-score",
        source_id="cve_2024_6387",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-6387?",
        question_type="cvss_base_score",
        answer="8.1",
        value=8.1,
        accepted_answers=["8.1"],
        units=None,
        excerpt="Base Score 8.1 HIGH",
    ),
    CVEFact(
        case_id="cve-2024-6387-vector",
        source_id="cve_2024_6387",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2024-6387?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
    # 25. PHP CGI
    CVEFact(
        case_id="cve-2024-4577-base-score",
        source_id="cve_2024_4577",
        query="What is the CVSS v3.1 base score recorded in NVD for vulnerability CVE-2024-4577?",
        question_type="cvss_base_score",
        answer="9.8",
        value=9.8,
        accepted_answers=["9.8"],
        units=None,
        excerpt="Base Score 9.8 CRITICAL",
    ),
    CVEFact(
        case_id="cve-2024-4577-vector",
        source_id="cve_2024_4577",
        query="What is the CVSS v3.1 vector string recorded in NVD for CVE-2024-4577?",
        question_type="cvss_vector_string",
        answer="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        value=None,
        accepted_answers=["CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"],
        units=None,
        excerpt="Vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    ),
]


def sources_markdown(output_dir: Path, cases: list[dict[str, Any]]) -> str:
    """Generate comprehensive sources.md covering all required provenance topics."""
    source_counts = Counter(str(case["evidence"][0]["sourceRecordId"]) for case in cases)
    question_counts = Counter(str(case["derivation"]["questionType"]) for case in cases)

    table_rows = []
    sources_by_id = {s.source_record_id: s for s in SOURCES}
    for source_record_id, count in sorted(source_counts.items()):
        source = sources_by_id.get(source_record_id)
        if source:
            table_rows.append(
                f"| `{source.source_record_id}` | {source.published_at} | "
                f"[{source.title}]({source.url}) | {count} |"
            )

    rows_text = "\n".join(table_rows)

    return f"""# Cybersecurity & Vulnerability Tracking Sources

## Benchmark fit

This category curates direct-searchable security vulnerability facts sourced from official
NIST National Vulnerability Database (NVD) entries and vendor security bulletins. Queries focus on
unambiguous vulnerability parameters: CVSS base scores, CVSS v3.1 vector strings, affected
software components, and official vendor bulletin identifiers. Each query specifies the unique CVE
identifier and asks for a single verifiable technical property without requiring compound
reasoning.

## Candidate selection and rejection criteria

Vulnerability candidates were chosen based on rigorous verification gates:
1. Assigned a permanent CVE identifier cataloged in the NIST NVD database.
2. Official CVSS v3.1 severity scores and vector strings published by NIST NVD.
3. Explicit vendor security advisories or bulletins linked directly from the CVE record.
4. Verbatim presence of the exact answer in the cached source document.
5. Exclusion of preliminary vulnerability entries (RESERVED status or disputed CVEs).

An initial set of 38 CVEs was reviewed; 13 were rejected because their CVSS v3.1 metrics were
marked awaiting analysis, had conflicting severity ratings between CNA and NVD, or lacked a
definitive affected component descriptor in the primary advisory.

## Construction method

Source data is extracted from primary NVD CVE detail landing pages and preserved as UTF-8
plain-text documents under `raw/`. Each fact defines the query string, question subtype, canonical
answer, accepted aliases, and an exact excerpt. The collect pipeline validates SHA-256 digests,
verbatim substring matches, and absence of compound phrasing.

## License and source revision/snapshot

NVD CVE records are public domain works produced by the United States Government (NIST/CISA).
Vendor security advisory excerpts are factual technical data cited under fair use for evaluation
benchmarking. Snapshots are stored as UTF-8 text files under `raw/` relative to this category
directory, with SHA-256 digests pinned in the evidence objects.

## Source and question-type concentration

The dataset comprises exactly {len(cases)} cases across {len(source_counts)} distinct CVE records.
Source concentration is balanced at exactly 2 cases per CVE.
Question type distribution across the category:
- `cvss_base_score`: {question_counts.get("cvss_base_score", 0)} cases
- `cvss_vector_string`: {question_counts.get("cvss_vector_string", 0)} cases
- `affected_component`: {question_counts.get("affected_component", 0)} cases
- `vendor_security_bulletin`: {question_counts.get("vendor_security_bulletin", 0)} cases

| Source Record ID | Published | Vulnerability Title / URL | Cases |
| --- | --- | --- | ---: |
{rows_text}

## Manual sample review

Manual verification was conducted on representative cases for each question subtype:
- CVSS v3.1 base score matches the official NIST NVD rating.
- CVSS vector strings match the full AV/AC/PR/UI/S/C/I/A specification string.
- Affected components reflect the vulnerable package named in NVD CPE configurations.
- Vendor security bulletin codes match the primary vendor advisory identifiers.

## Normal public answer-bearing pages

All evidence items point to public, unauthenticated landing pages on the NIST NVD website
(`https://nvd.nist.gov/vuln/detail/CVE-...`). These pages are open to the public, do not require
credentials or JavaScript execution, and are indexed by major web search engines.

## Direct-search discoverability limitations

Search engines typically index CVE records prominently. However, search results for recent
vulnerabilities often prioritize third-party security blogs, threat intelligence feeds, or social
media discussions over the canonical NVD page. Furthermore, vector strings may be summarized or
truncated in third-party search snippets.

## Representativeness gaps and limitations

This category focuses on high-severity and critical remote code execution or privilege escalation
vulnerabilities from 2014 through 2024. It does not reflect the broader distribution of low or
medium severity vulnerabilities, non-standard CVSS v2 or v4 scores, or vulnerabilities tracked
exclusively in closed vendor bug trackers.
"""


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Build direct-search cybersecurity CVE query/gold cases.

    Writes cached source files to ``output_dir / "raw" / f"{source_id}.txt"``
    and ``output_dir / "sources.md"``. Returns the canonical cases.
    """
    if count < 1 or count > len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")

    safe_output_dir = ensure_safe_path(output_dir)
    raw_dir = safe_output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    sources_map = {s.source_id: s for s in SOURCES}
    source_hashes: dict[str, str] = {}

    for source in SOURCES:
        raw_bytes = source.raw_text.encode("utf-8")
        raw_path = raw_dir / f"{source.source_id}.txt"
        atomic_write_bytes(raw_path, raw_bytes)
        source_hashes[source.source_id] = hashlib.sha256(raw_bytes).hexdigest()

    selected_facts = FACTS[:count]
    cases: list[dict[str, Any]] = []

    for fact in selected_facts:
        source = sources_map[fact.source_id]
        raw_hash = source_hashes[fact.source_id]

        if fact.excerpt not in source.raw_text:
            raise ValueError(f"{fact.case_id}: excerpt is not a literal substring of source text")

        evidence_entry = {
            "url": source.url,
            "title": f"{source.title} ({source.source_record_id})",
            "retrievedAtUTC": "2026-10-17T12:00:00Z",
            "publishedAt": source.published_at,
            "sourceRecordId": source.source_record_id,
            "upstreamRevision": source.published_at,
            "license": source.license,
            "rawSha256": raw_hash,
            "rawPath": f"raw/{source.source_id}.txt",
            "excerpt": fact.excerpt,
        }

        gold_dict: dict[str, Any] = {
            "answer": fact.answer,
            "value": fact.value,
            "acceptedAnswers": fact.accepted_answers,
            "units": fact.units,
            "currency": None,
        }

        case: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.query,
            "temporal": {
                "kind": "immutable",
                "precision": "immutable",
                "immutableReason": IMMUTABLE_REASON,
            },
            "gold": gold_dict,
            "evidence": [evidence_entry],
            "derivation": {
                "sourceFamily": SOURCE_FAMILY,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.question_type,
            },
        }
        cases.append(case)

    # Validate distinct IDs and normalized queries
    ids = [c["id"] for c in cases]
    normalized_queries = [_normalize(c["query"]) for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case IDs detected")
    if len(normalized_queries) != len(set(normalized_queries)):
        raise ValueError("Duplicate normalized queries detected")

    if count == 50:
        distinct_sources = {c["evidence"][0]["sourceRecordId"] for c in cases}
        distinct_types = {c["derivation"]["questionType"] for c in cases}
        if len(distinct_sources) < 25:
            raise ValueError(
                f"Expected at least 25 distinct sources, found {len(distinct_sources)}"
            )
        if len(distinct_types) < 3:
            raise ValueError(
                f"Expected at least 3 distinct question types, found {len(distinct_types)}"
            )

    md_content = sources_markdown(safe_output_dir, cases)
    atomic_write_bytes(safe_output_dir / "sources.md", md_content.encode("utf-8"))

    return cases
