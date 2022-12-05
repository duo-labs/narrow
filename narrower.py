# // Copyright 2022 Cisco Systems, Inc.
# //
# // Licensed under the Apache License, Version 2.0 (the "License");
# // you may not use this file except in compliance with the License.
# // You may obtain a copy of the License at
# //
# // http://www.apache.org/licenses/LICENSE-2.0
# //
# // Unless required by applicable law or agreed to in writing, software
# // distributed under the License is distributed on an "AS IS" BASIS,
# // WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# // See the License for the specific language governing permissions and
# // limitations under the License.

# This class is responsible for taking an input file and reducing the priority of
# vulns that can't be found by narrow.
# For now the following formats are supported:
#   1. https://wiki.duosec.org/display/Security/Creating+and+Using+SEP+Plugins#CreatingandUsingSEPPlugins-sca-with-vuln-findings:SoftwareCompositionAnalysisResults
import copy
from datetime import date
import json
from typing import List
import jsonschema

from patch_extractor import PatchExtractor
import cfg
import cvsslib

# CycloneDX Schema
# https://raw.githubusercontent.com/CycloneDX/specification/eb7b3c9e188a16ce23f2c11ba6468da50804d286/schema/bom-1.4.schema.json
STANDARD_SCA_SCHEMA = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "http://cyclonedx.org/schema/bom-1.4.schema.json",
  "type": "object",
  "title": "CycloneDX Software Bill of Materials Standard",
  "$comment" : "CycloneDX JSON schema is published under the terms of the Apache License 2.0.",
  "required": [
    "bomFormat",
    "specVersion",
    "version"
  ],
  "additionalProperties": False,
  "properties": {
    "$schema": {
      "type": "string",
      "enum": [
        "http://cyclonedx.org/schema/bom-1.4.schema.json"
      ]
    },
    "bomFormat": {
      "type": "string",
      "title": "BOM Format",
      "description": "Specifies the format of the BOM. This helps to identify the file as CycloneDX since BOMs do not have a filename convention nor does JSON schema support namespaces. This value MUST be \"CycloneDX\".",
      "enum": [
        "CycloneDX"
      ]
    },
    "specVersion": {
      "type": "string",
      "title": "CycloneDX Specification Version",
      "description": "The version of the CycloneDX specification a BOM conforms to (starting at version 1.2).",
      "examples": ["1.4"]
    },
    "serialNumber": {
      "type": "string",
      "title": "BOM Serial Number",
      "description": "Every BOM generated SHOULD have a unique serial number, even if the contents of the BOM have not changed over time. If specified, the serial number MUST conform to RFC-4122. Use of serial numbers are RECOMMENDED.",
      "examples": ["urn:uuid:3e671687-395b-41f5-a30f-a58921a69b79"],
      "pattern": "^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    },
    "version": {
      "type": "integer",
      "title": "BOM Version",
      "description": "Whenever an existing BOM is modified, either manually or through automated processes, the version of the BOM SHOULD be incremented by 1. When a system is presented with multiple BOMs with identical serial numbers, the system SHOULD use the most recent version of the BOM. The default version is '1'.",
      "default": 1,
      "examples": [1]
    },
    "metadata": {
      "$ref": "#/definitions/metadata",
      "title": "BOM Metadata",
      "description": "Provides additional information about a BOM."
    },
    "components": {
      "type": "array",
      "additionalItems": False,
      "items": {"$ref": "#/definitions/component"},
      "uniqueItems": True,
      "title": "Components",
      "description": "A list of software and hardware components."
    },
    "services": {
      "type": "array",
      "additionalItems": False,
      "items": {"$ref": "#/definitions/service"},
      "uniqueItems": True,
      "title": "Services",
      "description": "A list of services. This may include microservices, function-as-a-service, and other types of network or intra-process services."
    },
    "externalReferences": {
      "type": "array",
      "additionalItems": False,
      "items": {"$ref": "#/definitions/externalReference"},
      "title": "External References",
      "description": "External references provide a way to document systems, sites, and information that may be relevant but which are not included with the BOM."
    },
    "dependencies": {
      "type": "array",
      "additionalItems": False,
      "items": {"$ref": "#/definitions/dependency"},
      "uniqueItems": True,
      "title": "Dependencies",
      "description": "Provides the ability to document dependency relationships."
    },
    "compositions": {
      "type": "array",
      "additionalItems": False,
      "items": {"$ref": "#/definitions/compositions"},
      "uniqueItems": True,
      "title": "Compositions",
      "description": "Compositions describe constituent parts (including components, services, and dependency relationships) and their completeness."
    },
    "vulnerabilities": {
      "type": "array",
      "additionalItems": False,
      "items": {"$ref": "#/definitions/vulnerability"},
      "uniqueItems": True,
      "title": "Vulnerabilities",
      "description": "Vulnerabilities identified in components or services."
    },
    "signature": {
      "$ref": "#/definitions/signature",
      "title": "Signature",
      "description": "Enveloped signature in [JSON Signature Format (JSF)](https://cyberphone.github.io/doc/security/jsf.html)."
    }
  },
  "definitions": {
    "refType": {
      "$comment": "Identifier-DataType for interlinked elements.",
      "type": "string"
    },
    "metadata": {
      "type": "object",
      "title": "BOM Metadata Object",
      "additionalProperties": False,
      "properties": {
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "title": "Timestamp",
          "description": "The date and time (timestamp) when the BOM was created."
        },
        "tools": {
          "type": "array",
          "title": "Creation Tools",
          "description": "The tool(s) used in the creation of the BOM.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/tool"}
        },
        "authors" :{
          "type": "array",
          "title": "Authors",
          "description": "The person(s) who created the BOM. Authors are common in BOMs created through manual processes. BOMs created through automated means may not have authors.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/organizationalContact"}
        },
        "component": {
          "title": "Component",
          "description": "The component that the BOM describes.",
          "$ref": "#/definitions/component"
        },
        "manufacture": {
          "title": "Manufacture",
          "description": "The organization that manufactured the component that the BOM describes.",
          "$ref": "#/definitions/organizationalEntity"
        },
        "supplier": {
          "title": "Supplier",
          "description": " The organization that supplied the component that the BOM describes. The supplier may often be the manufacturer, but may also be a distributor or repackager.",
          "$ref": "#/definitions/organizationalEntity"
        },
        "licenses": {
          "type": "array",
          "title": "BOM License(s)",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/licenseChoice"}
        },
        "properties": {
          "type": "array",
          "title": "Properties",
          "description": "Provides the ability to document properties in a name-value store. This provides flexibility to include data not officially supported in the standard without having to use additional namespaces or create extensions. Unlike key-value stores, properties support duplicate names, each potentially having different values. Property names of interest to the general public are encouraged to be registered in the [CycloneDX Property Taxonomy](https://github.com/CycloneDX/cyclonedx-property-taxonomy). Formal registration is OPTIONAL.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/property"}
        }
      }
    },
    "tool": {
      "type": "object",
      "title": "Tool",
      "description": "Information about the automated or manual tool used",
      "additionalProperties": False,
      "properties": {
        "vendor": {
          "type": "string",
          "title": "Tool Vendor",
          "description": "The name of the vendor who created the tool"
        },
        "name": {
          "type": "string",
          "title": "Tool Name",
          "description": "The name of the tool"
        },
        "version": {
          "type": "string",
          "title": "Tool Version",
          "description": "The version of the tool"
        },
        "hashes": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/hash"},
          "title": "Hashes",
          "description": "The hashes of the tool (if applicable)."
        },
        "externalReferences": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/externalReference"},
          "title": "External References",
          "description": "External references provide a way to document systems, sites, and information that may be relevant but which are not included with the BOM."
        }
      }
    },
    "organizationalEntity": {
      "type": "object",
      "title": "Organizational Entity Object",
      "description": "",
      "additionalProperties": False,
      "properties": {
        "name": {
          "type": "string",
          "title": "Name",
          "description": "The name of the organization",
          "examples": [
            "Example Inc."
          ]
        },
        "url": {
          "type": "array",
          "items": {
            "type": "string",
            "format": "iri-reference"
          },
          "title": "URL",
          "description": "The URL of the organization. Multiple URLs are allowed.",
          "examples": ["https://example.com"]
        },
        "contact": {
          "type": "array",
          "title": "Contact",
          "description": "A contact at the organization. Multiple contacts are allowed.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/organizationalContact"}
        }
      }
    },
    "organizationalContact": {
      "type": "object",
      "title": "Organizational Contact Object",
      "description": "",
      "additionalProperties": False,
      "properties": {
        "name": {
          "type": "string",
          "title": "Name",
          "description": "The name of a contact",
          "examples": ["Contact name"]
        },
        "email": {
          "type": "string",
          "format": "idn-email",
          "title": "Email Address",
          "description": "The email address of the contact.",
          "examples": ["firstname.lastname@example.com"]
        },
        "phone": {
          "type": "string",
          "title": "Phone",
          "description": "The phone number of the contact.",
          "examples": ["800-555-1212"]
        }
      }
    },
    "component": {
      "type": "object",
      "title": "Component Object",
      "required": [
        "type",
        "name"
      ],
      "additionalProperties": False,
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "application",
            "framework",
            "library",
            "container",
            "operating-system",
            "device",
            "firmware",
            "file"
          ],
          "title": "Component Type",
          "description": "Specifies the type of component. For software components, classify as application if no more specific appropriate classification is available or cannot be determined for the component. Types include:\n\n* __application__ = A software application. Refer to [https://en.wikipedia.org/wiki/Application_software](https://en.wikipedia.org/wiki/Application_software) for information about applications.\n* __framework__ = A software framework. Refer to [https://en.wikipedia.org/wiki/Software_framework](https://en.wikipedia.org/wiki/Software_framework) for information on how frameworks vary slightly from libraries.\n* __library__ = A software library. Refer to [https://en.wikipedia.org/wiki/Library_(computing)](https://en.wikipedia.org/wiki/Library_(computing))\n for information about libraries. All third-party and open source reusable components will likely be a library. If the library also has key features of a framework, then it should be classified as a framework. If not, or is unknown, then specifying library is RECOMMENDED.\n* __container__ = A packaging and/or runtime format, not specific to any particular technology, which isolates software inside the container from software outside of a container through virtualization technology. Refer to [https://en.wikipedia.org/wiki/OS-level_virtualization](https://en.wikipedia.org/wiki/OS-level_virtualization)\n* __operating-system__ = A software operating system without regard to deployment model (i.e. installed on physical hardware, virtual machine, image, etc) Refer to [https://en.wikipedia.org/wiki/Operating_system](https://en.wikipedia.org/wiki/Operating_system)\n* __device__ = A hardware device such as a processor, or chip-set. A hardware device containing firmware SHOULD include a component for the physical hardware itself, and another component of type 'firmware' or 'operating-system' (whichever is relevant), describing information about the software running on the device.\n* __firmware__ = A special type of software that provides low-level control over a devices hardware. Refer to [https://en.wikipedia.org/wiki/Firmware](https://en.wikipedia.org/wiki/Firmware)\n* __file__ = A computer file. Refer to [https://en.wikipedia.org/wiki/Computer_file](https://en.wikipedia.org/wiki/Computer_file) for information about files.",
          "examples": ["library"]
        },
        "mime-type": {
          "type": "string",
          "title": "Mime-Type",
          "description": "The optional mime-type of the component. When used on file components, the mime-type can provide additional context about the kind of file being represented such as an image, font, or executable. Some library or framework components may also have an associated mime-type.",
          "examples": ["image/jpeg"],
          "pattern": "^[-+a-z0-9.]+/[-+a-z0-9.]+$"
        },
        "bom-ref": {
          "$ref": "#/definitions/refType",
          "title": "BOM Reference",
          "description": "An optional identifier which can be used to reference the component elsewhere in the BOM. Every bom-ref MUST be unique within the BOM."
        },
        "supplier": {
          "title": "Component Supplier",
          "description": " The organization that supplied the component. The supplier may often be the manufacturer, but may also be a distributor or repackager.",
          "$ref": "#/definitions/organizationalEntity"
        },
        "author": {
          "type": "string",
          "title": "Component Author",
          "description": "The person(s) or organization(s) that authored the component",
          "examples": ["Acme Inc"]
        },
        "publisher": {
          "type": "string",
          "title": "Component Publisher",
          "description": "The person(s) or organization(s) that published the component",
          "examples": ["Acme Inc"]
        },
        "group": {
          "type": "string",
          "title": "Component Group",
          "description": "The grouping name or identifier. This will often be a shortened, single name of the company or project that produced the component, or the source package or domain name. Whitespace and special characters should be avoided. Examples include: apache, org.apache.commons, and apache.org.",
          "examples": ["com.acme"]
        },
        "name": {
          "type": "string",
          "title": "Component Name",
          "description": "The name of the component. This will often be a shortened, single name of the component. Examples: commons-lang3 and jquery",
          "examples": ["tomcat-catalina"]
        },
        "version": {
          "type": "string",
          "title": "Component Version",
          "description": "The component version. The version should ideally comply with semantic versioning but is not enforced.",
          "examples": ["9.0.14"]
        },
        "description": {
          "type": "string",
          "title": "Component Description",
          "description": "Specifies a description for the component"
        },
        "scope": {
          "type": "string",
          "enum": [
            "required",
            "optional",
            "excluded"
          ],
          "title": "Component Scope",
          "description": "Specifies the scope of the component. If scope is not specified, 'required' scope SHOULD be assumed by the consumer of the BOM.",
          "default": "required"
        },
        "hashes": {
          "type": "array",
          "title": "Component Hashes",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/hash"}
        },
        "licenses": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/licenseChoice"},
          "title": "Component License(s)"
        },
        "copyright": {
          "type": "string",
          "title": "Component Copyright",
          "description": "A copyright notice informing users of the underlying claims to copyright ownership in a published work.",
          "examples": ["Acme Inc"]
        },
        "cpe": {
          "type": "string",
          "title": "Component Common Platform Enumeration (CPE)",
          "description": "Specifies a well-formed CPE name that conforms to the CPE 2.2 or 2.3 specification. See [https://nvd.nist.gov/products/cpe](https://nvd.nist.gov/products/cpe)",
          "examples": ["cpe:2.3:a:acme:component_framework:-:*:*:*:*:*:*:*"]
        },
        "purl": {
          "type": "string",
          "title": "Component Package URL (purl)",
          "description": "Specifies the package-url (purl). The purl, if specified, MUST be valid and conform to the specification defined at: [https://github.com/package-url/purl-spec](https://github.com/package-url/purl-spec)",
          "examples": ["pkg:maven/com.acme/tomcat-catalina@9.0.14?packaging=jar"]
        },
        "swid": {
          "$ref": "#/definitions/swid",
          "title": "SWID Tag",
          "description": "Specifies metadata and content for [ISO-IEC 19770-2 Software Identification (SWID) Tags](https://www.iso.org/standard/65666.html)."
        },
        "modified": {
          "type": "boolean",
          "title": "Component Modified From Original",
          "description": "[Deprecated] - DO NOT USE. This will be removed in a future version. Use the pedigree element instead to supply information on exactly how the component was modified. A boolean value indicating if the component has been modified from the original. A value of true indicates the component is a derivative of the original. A value of false indicates the component has not been modified from the original."
        },
        "pedigree": {
          "type": "object",
          "title": "Component Pedigree",
          "description": "Component pedigree is a way to document complex supply chain scenarios where components are created, distributed, modified, redistributed, combined with other components, etc. Pedigree supports viewing this complex chain from the beginning, the end, or anywhere in the middle. It also provides a way to document variants where the exact relation may not be known.",
          "additionalProperties": False,
          "properties": {
            "ancestors": {
              "type": "array",
              "title": "Ancestors",
              "description": "Describes zero or more components in which a component is derived from. This is commonly used to describe forks from existing projects where the forked version contains a ancestor node containing the original component it was forked from. For example, Component A is the original component. Component B is the component being used and documented in the BOM. However, Component B contains a pedigree node with a single ancestor documenting Component A - the original component from which Component B is derived from.",
              "additionalItems": False,
              "items": {"$ref": "#/definitions/component"}
            },
            "descendants": {
              "type": "array",
              "title": "Descendants",
              "description": "Descendants are the exact opposite of ancestors. This provides a way to document all forks (and their forks) of an original or root component.",
              "additionalItems": False,
              "items": {"$ref": "#/definitions/component"}
            },
            "variants": {
              "type": "array",
              "title": "Variants",
              "description": "Variants describe relations where the relationship between the components are not known. For example, if Component A contains nearly identical code to Component B. They are both related, but it is unclear if one is derived from the other, or if they share a common ancestor.",
              "additionalItems": False,
              "items": {"$ref": "#/definitions/component"}
            },
            "commits": {
              "type": "array",
              "title": "Commits",
              "description": "A list of zero or more commits which provide a trail describing how the component deviates from an ancestor, descendant, or variant.",
              "additionalItems": False,
              "items": {"$ref": "#/definitions/commit"}
            },
            "patches": {
              "type": "array",
              "title": "Patches",
              "description": ">A list of zero or more patches describing how the component deviates from an ancestor, descendant, or variant. Patches may be complimentary to commits or may be used in place of commits.",
              "additionalItems": False,
              "items": {"$ref": "#/definitions/patch"}
            },
            "notes": {
              "type": "string",
              "title": "Notes",
              "description": "Notes, observations, and other non-structured commentary describing the components pedigree."
            }
          }
        },
        "externalReferences": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/externalReference"},
          "title": "External References",
          "description": "External references provide a way to document systems, sites, and information that may be relevant but which are not included with the BOM."
        },
        "components": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/component"},
          "uniqueItems": True,
          "title": "Components",
          "description": "A list of software and hardware components included in the parent component. This is not a dependency tree. It provides a way to specify a hierarchical representation of component assemblies, similar to system &#8594; subsystem &#8594; parts assembly in physical supply chains."
        },
        "evidence": {
          "$ref": "#/definitions/componentEvidence",
          "title": "Evidence",
          "description": "Provides the ability to document evidence collected through various forms of extraction or analysis."
        },
        "releaseNotes": {
          "$ref": "#/definitions/releaseNotes",
          "title": "Release notes",
          "description": "Specifies optional release notes."
        },
        "properties": {
          "type": "array",
          "title": "Properties",
          "description": "Provides the ability to document properties in a name-value store. This provides flexibility to include data not officially supported in the standard without having to use additional namespaces or create extensions. Unlike key-value stores, properties support duplicate names, each potentially having different values. Property names of interest to the general public are encouraged to be registered in the [CycloneDX Property Taxonomy](https://github.com/CycloneDX/cyclonedx-property-taxonomy). Formal registration is OPTIONAL.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/property"}
        },
        "signature": {
          "$ref": "#/definitions/signature",
          "title": "Signature",
          "description": "Enveloped signature in [JSON Signature Format (JSF)](https://cyberphone.github.io/doc/security/jsf.html)."
        }
      }
    },
    "swid": {
      "type": "object",
      "title": "SWID Tag",
      "description": "Specifies metadata and content for ISO-IEC 19770-2 Software Identification (SWID) Tags.",
      "required": [
        "tagId",
        "name"
      ],
      "additionalProperties": False,
      "properties": {
        "tagId": {
          "type": "string",
          "title": "Tag ID",
          "description": "Maps to the tagId of a SoftwareIdentity."
        },
        "name": {
          "type": "string",
          "title": "Name",
          "description": "Maps to the name of a SoftwareIdentity."
        },
        "version": {
          "type": "string",
          "title": "Version",
          "default": "0.0",
          "description": "Maps to the version of a SoftwareIdentity."
        },
        "tagVersion": {
          "type": "integer",
          "title": "Tag Version",
          "default": 0,
          "description": "Maps to the tagVersion of a SoftwareIdentity."
        },
        "patch": {
          "type": "boolean",
          "title": "Patch",
          "default": False,
          "description": "Maps to the patch of a SoftwareIdentity."
        },
        "text": {
          "title": "Attachment text",
          "description": "Specifies the metadata and content of the SWID tag.",
          "$ref": "#/definitions/attachment"
        },
        "url": {
          "type": "string",
          "title": "URL",
          "description": "The URL to the SWID file.",
          "format": "iri-reference"
        }
      }
    },
    "attachment": {
      "type": "object",
      "title": "Attachment",
      "description": "Specifies the metadata and content for an attachment.",
      "required": [
        "content"
      ],
      "additionalProperties": False,
      "properties": {
        "contentType": {
          "type": "string",
          "title": "Content-Type",
          "description": "Specifies the content type of the text. Defaults to text/plain if not specified.",
          "default": "text/plain"
        },
        "encoding": {
          "type": "string",
          "title": "Encoding",
          "description": "Specifies the optional encoding the text is represented in.",
          "enum": [
            "base64"
          ]
        },
        "content": {
          "type": "string",
          "title": "Attachment Text",
          "description": "The attachment data. Proactive controls such as input validation and sanitization should be employed to prevent misuse of attachment text."
        }
      }
    },
    "hash": {
      "type": "object",
      "title": "Hash Objects",
      "required": [
        "alg",
        "content"
      ],
      "additionalProperties": False,
      "properties": {
        "alg": {
          "$ref": "#/definitions/hash-alg"
        },
        "content": {
          "$ref": "#/definitions/hash-content"
        }
      }
    },
    "hash-alg": {
      "type": "string",
      "enum": [
        "MD5",
        "SHA-1",
        "SHA-256",
        "SHA-384",
        "SHA-512",
        "SHA3-256",
        "SHA3-384",
        "SHA3-512",
        "BLAKE2b-256",
        "BLAKE2b-384",
        "BLAKE2b-512",
        "BLAKE3"
      ],
      "title": "Hash Algorithm"
    },
    "hash-content": {
      "type": "string",
      "title": "Hash Content (value)",
      "examples": ["3942447fac867ae5cdb3229b658f4d48"],
      "pattern": "^([a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64}|[a-fA-F0-9]{96}|[a-fA-F0-9]{128})$"
    },
    "license": {
      "type": "object",
      "title": "License Object",
      "oneOf": [
        {
          "required": ["id"]
        },
        {
          "required": ["name"]
        }
      ],
      "additionalProperties": False,
      "properties": {
        "id": {
          "$ref": "spdx.schema.json",
          "title": "License ID (SPDX)",
          "description": "A valid SPDX license ID",
          "examples": ["Apache-2.0"]
        },
        "name": {
          "type": "string",
          "title": "License Name",
          "description": "If SPDX does not define the license used, this field may be used to provide the license name",
          "examples": ["Acme Software License"]
        },
        "text": {
          "title": "License text",
          "description": "An optional way to include the textual content of a license.",
          "$ref": "#/definitions/attachment"
        },
        "url": {
          "type": "string",
          "title": "License URL",
          "description": "The URL to the license file. If specified, a 'license' externalReference should also be specified for completeness",
          "examples": ["https://www.apache.org/licenses/LICENSE-2.0.txt"],
          "format": "iri-reference"
        }
      }
    },
    "licenseChoice": {
      "type": "object",
      "title": "License(s)",
      "additionalProperties": False,
      "properties": {
        "license": {
          "$ref": "#/definitions/license"
        },
        "expression": {
          "type": "string",
          "title": "SPDX License Expression",
          "examples": [
            "Apache-2.0 AND (MIT OR GPL-2.0-only)",
            "GPL-3.0-only WITH Classpath-exception-2.0"
          ]
        }
      },
      "oneOf":[
        {
          "required": ["license"]
        },
        {
          "required": ["expression"]
        }
      ]
    },
    "commit": {
      "type": "object",
      "title": "Commit",
      "description": "Specifies an individual commit",
      "additionalProperties": False,
      "properties": {
        "uid": {
          "type": "string",
          "title": "UID",
          "description": "A unique identifier of the commit. This may be version control specific. For example, Subversion uses revision numbers whereas git uses commit hashes."
        },
        "url": {
          "type": "string",
          "title": "URL",
          "description": "The URL to the commit. This URL will typically point to a commit in a version control system.",
          "format": "iri-reference"
        },
        "author": {
          "title": "Author",
          "description": "The author who created the changes in the commit",
          "$ref": "#/definitions/identifiableAction"
        },
        "committer": {
          "title": "Committer",
          "description": "The person who committed or pushed the commit",
          "$ref": "#/definitions/identifiableAction"
        },
        "message": {
          "type": "string",
          "title": "Message",
          "description": "The text description of the contents of the commit"
        }
      }
    },
    "patch": {
      "type": "object",
      "title": "Patch",
      "description": "Specifies an individual patch",
      "required": [
        "type"
      ],
      "additionalProperties": False,
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "unofficial",
            "monkey",
            "backport",
            "cherry-pick"
          ],
          "title": "Type",
          "description": "Specifies the purpose for the patch including the resolution of defects, security issues, or new behavior or functionality.\n\n* __unofficial__ = A patch which is not developed by the creators or maintainers of the software being patched. Refer to [https://en.wikipedia.org/wiki/Unofficial_patch](https://en.wikipedia.org/wiki/Unofficial_patch)\n* __monkey__ = A patch which dynamically modifies runtime behavior. Refer to [https://en.wikipedia.org/wiki/Monkey_patch](https://en.wikipedia.org/wiki/Monkey_patch)\n* __backport__ = A patch which takes code from a newer version of software and applies it to older versions of the same software. Refer to [https://en.wikipedia.org/wiki/Backporting](https://en.wikipedia.org/wiki/Backporting)\n* __cherry-pick__ = A patch created by selectively applying commits from other versions or branches of the same software."
        },
        "diff": {
          "title": "Diff",
          "description": "The patch file (or diff) that show changes. Refer to [https://en.wikipedia.org/wiki/Diff](https://en.wikipedia.org/wiki/Diff)",
          "$ref": "#/definitions/diff"
        },
        "resolves": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/issue"},
          "title": "Resolves",
          "description": "A collection of issues the patch resolves"
        }
      }
    },
    "diff": {
      "type": "object",
      "title": "Diff",
      "description": "The patch file (or diff) that show changes. Refer to https://en.wikipedia.org/wiki/Diff",
      "additionalProperties": False,
      "properties": {
        "text": {
          "title": "Diff text",
          "description": "Specifies the optional text of the diff",
          "$ref": "#/definitions/attachment"
        },
        "url": {
          "type": "string",
          "title": "URL",
          "description": "Specifies the URL to the diff",
          "format": "iri-reference"
        }
      }
    },
    "issue": {
      "type": "object",
      "title": "Diff",
      "description": "An individual issue that has been resolved.",
      "required": [
        "type"
      ],
      "additionalProperties": False,
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "defect",
            "enhancement",
            "security"
          ],
          "title": "Type",
          "description": "Specifies the type of issue"
        },
        "id": {
          "type": "string",
          "title": "ID",
          "description": "The identifier of the issue assigned by the source of the issue"
        },
        "name": {
          "type": "string",
          "title": "Name",
          "description": "The name of the issue"
        },
        "description": {
          "type": "string",
          "title": "Description",
          "description": "A description of the issue"
        },
        "source": {
          "type": "object",
          "title": "Source",
          "description": "The source of the issue where it is documented",
          "additionalProperties": False,
          "properties": {
            "name": {
              "type": "string",
              "title": "Name",
              "description": "The name of the source. For example 'National Vulnerability Database', 'NVD', and 'Apache'"
            },
            "url": {
              "type": "string",
              "title": "URL",
              "description": "The url of the issue documentation as provided by the source",
              "format": "iri-reference"
            }
          }
        },
        "references": {
          "type": "array",
          "items": {
            "type": "string",
            "format": "iri-reference"
          },
          "title": "References",
          "description": "A collection of URL's for reference. Multiple URLs are allowed.",
          "examples": ["https://example.com"]
        }
      }
    },
    "identifiableAction": {
      "type": "object",
      "title": "Identifiable Action",
      "description": "Specifies an individual commit",
      "additionalProperties": False,
      "properties": {
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "title": "Timestamp",
          "description": "The timestamp in which the action occurred"
        },
        "name": {
          "type": "string",
          "title": "Name",
          "description": "The name of the individual who performed the action"
        },
        "email": {
          "type": "string",
          "format": "idn-email",
          "title": "E-mail",
          "description": "The email address of the individual who performed the action"
        }
      }
    },
    "externalReference": {
      "type": "object",
      "title": "External Reference",
      "description": "Specifies an individual external reference",
      "required": [
        "url",
        "type"
      ],
      "additionalProperties": False,
      "properties": {
        "url": {
          "type": "string",
          "title": "URL",
          "description": "The URL to the external reference",
          "format": "iri-reference"
        },
        "comment": {
          "type": "string",
          "title": "Comment",
          "description": "An optional comment describing the external reference"
        },
        "type": {
          "type": "string",
          "title": "Type",
          "description": "Specifies the type of external reference. There are built-in types to describe common references. If a type does not exist for the reference being referred to, use the \"other\" type.",
          "enum": [
            "vcs",
            "issue-tracker",
            "website",
            "advisories",
            "bom",
            "mailing-list",
            "social",
            "chat",
            "documentation",
            "support",
            "distribution",
            "license",
            "build-meta",
            "build-system",
            "release-notes",
            "other"
          ]
        },
        "hashes": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/hash"},
          "title": "Hashes",
          "description": "The hashes of the external reference (if applicable)."
        }
      }
    },
    "dependency": {
      "type": "object",
      "title": "Dependency",
      "description": "Defines the direct dependencies of a component. Components that do not have their own dependencies MUST be declared as empty elements within the graph. Components that are not represented in the dependency graph MAY have unknown dependencies. It is RECOMMENDED that implementations assume this to be opaque and not an indicator of a component being dependency-free.",
      "required": [
        "ref"
      ],
      "additionalProperties": False,
      "properties": {
        "ref": {
          "$ref": "#/definitions/refType",
          "title": "Reference",
          "description": "References a component by the components bom-ref attribute"
        },
        "dependsOn": {
          "type": "array",
          "uniqueItems": True,
          "additionalItems": False,
          "items": {
            "$ref": "#/definitions/refType"
          },
          "title": "Depends On",
          "description": "The bom-ref identifiers of the components that are dependencies of this dependency object."
        }
      }
    },
    "service": {
      "type": "object",
      "title": "Service Object",
      "required": [
        "name"
      ],
      "additionalProperties": False,
      "properties": {
        "bom-ref": {
          "$ref": "#/definitions/refType",
          "title": "BOM Reference",
          "description": "An optional identifier which can be used to reference the service elsewhere in the BOM. Every bom-ref MUST be unique within the BOM."
        },
        "provider": {
          "title": "Provider",
          "description": "The organization that provides the service.",
          "$ref": "#/definitions/organizationalEntity"
        },
        "group": {
          "type": "string",
          "title": "Service Group",
          "description": "The grouping name, namespace, or identifier. This will often be a shortened, single name of the company or project that produced the service or domain name. Whitespace and special characters should be avoided.",
          "examples": ["com.acme"]
        },
        "name": {
          "type": "string",
          "title": "Service Name",
          "description": "The name of the service. This will often be a shortened, single name of the service.",
          "examples": ["ticker-service"]
        },
        "version": {
          "type": "string",
          "title": "Service Version",
          "description": "The service version.",
          "examples": ["1.0.0"]
        },
        "description": {
          "type": "string",
          "title": "Service Description",
          "description": "Specifies a description for the service"
        },
        "endpoints": {
          "type": "array",
          "items": {
            "type": "string",
            "format": "iri-reference"
          },
          "title": "Endpoints",
          "description": "The endpoint URIs of the service. Multiple endpoints are allowed.",
          "examples": ["https://example.com/api/v1/ticker"]
        },
        "authenticated": {
          "type": "boolean",
          "title": "Authentication Required",
          "description": "A boolean value indicating if the service requires authentication. A value of true indicates the service requires authentication prior to use. A value of false indicates the service does not require authentication."
        },
        "x-trust-boundary": {
          "type": "boolean",
          "title": "Crosses Trust Boundary",
          "description": "A boolean value indicating if use of the service crosses a trust zone or boundary. A value of true indicates that by using the service, a trust boundary is crossed. A value of false indicates that by using the service, a trust boundary is not crossed."
        },
        "data": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/dataClassification"},
          "title": "Data Classification",
          "description": "Specifies the data classification."
        },
        "licenses": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/licenseChoice"},
          "title": "Component License(s)"
        },
        "externalReferences": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/externalReference"},
          "title": "External References",
          "description": "External references provide a way to document systems, sites, and information that may be relevant but which are not included with the BOM."
        },
        "services": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/service"},
          "uniqueItems": True,
          "title": "Services",
          "description": "A list of services included or deployed behind the parent service. This is not a dependency tree. It provides a way to specify a hierarchical representation of service assemblies."
        },
        "releaseNotes": {
          "$ref": "#/definitions/releaseNotes",
          "title": "Release notes",
          "description": "Specifies optional release notes."
        },
        "properties": {
          "type": "array",
          "title": "Properties",
          "description": "Provides the ability to document properties in a name-value store. This provides flexibility to include data not officially supported in the standard without having to use additional namespaces or create extensions. Unlike key-value stores, properties support duplicate names, each potentially having different values. Property names of interest to the general public are encouraged to be registered in the [CycloneDX Property Taxonomy](https://github.com/CycloneDX/cyclonedx-property-taxonomy). Formal registration is OPTIONAL.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/property"}
        },
        "signature": {
          "$ref": "#/definitions/signature",
          "title": "Signature",
          "description": "Enveloped signature in [JSON Signature Format (JSF)](https://cyberphone.github.io/doc/security/jsf.html)."
        }
      }
    },
    "dataClassification": {
      "type": "object",
      "title": "Hash Objects",
      "required": [
        "flow",
        "classification"
      ],
      "additionalProperties": False,
      "properties": {
        "flow": {
          "$ref": "#/definitions/dataFlow",
          "title": "Directional Flow",
          "description": "Specifies the flow direction of the data. Direction is relative to the service. Inbound flow states that data enters the service. Outbound flow states that data leaves the service. Bi-directional states that data flows both ways, and unknown states that the direction is not known."
        },
        "classification": {
          "type": "string",
          "title": "Classification",
          "description": "Data classification tags data according to its type, sensitivity, and value if altered, stolen, or destroyed."
        }
      }
    },
    "dataFlow": {
      "type": "string",
      "enum": [
        "inbound",
        "outbound",
        "bi-directional",
        "unknown"
      ],
      "title": "Data flow direction",
      "description": "Specifies the flow direction of the data. Direction is relative to the service. Inbound flow states that data enters the service. Outbound flow states that data leaves the service. Bi-directional states that data flows both ways, and unknown states that the direction is not known."
    },

    "copyright": {
      "type": "object",
      "title": "Copyright",
      "required": [
        "text"
      ],
      "additionalProperties": False,
      "properties": {
        "text": {
          "type": "string",
          "title": "Copyright Text"
        }
      }
    },

    "componentEvidence": {
      "type": "object",
      "title": "Evidence",
      "description": "Provides the ability to document evidence collected through various forms of extraction or analysis.",
      "additionalProperties": False,
      "properties": {
        "licenses": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/licenseChoice"},
          "title": "Component License(s)"
        },
        "copyright": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/copyright"},
          "title": "Copyright"
        }
      }
    },
    "compositions": {
      "type": "object",
      "title": "Compositions",
      "required": [
        "aggregate"
      ],
      "additionalProperties": False,
      "properties": {
        "aggregate": {
          "$ref": "#/definitions/aggregateType",
          "title": "Aggregate",
          "description": "Specifies an aggregate type that describe how complete a relationship is."
        },
        "assemblies": {
          "type": "array",
          "uniqueItems": True,
          "items": {
            "type": "string"
          },
          "title": "BOM references",
          "description": "The bom-ref identifiers of the components or services being described. Assemblies refer to nested relationships whereby a constituent part may include other constituent parts. References do not cascade to child parts. References are explicit for the specified constituent part only."
        },
        "dependencies": {
          "type": "array",
          "uniqueItems": True,
          "items": {
            "type": "string"
          },
          "title": "BOM references",
          "description": "The bom-ref identifiers of the components or services being described. Dependencies refer to a relationship whereby an independent constituent part requires another independent constituent part. References do not cascade to transitive dependencies. References are explicit for the specified dependency only."
        },
        "signature": {
          "$ref": "#/definitions/signature",
          "title": "Signature",
          "description": "Enveloped signature in [JSON Signature Format (JSF)](https://cyberphone.github.io/doc/security/jsf.html)."
        }
      }
    },
    "aggregateType": {
      "type": "string",
      "default": "not_specified",
      "enum": [
        "complete",
        "incomplete",
        "incomplete_first_party_only",
        "incomplete_third_party_only",
        "unknown",
        "not_specified"
      ]
    },
    "property": {
      "type": "object",
      "title": "Lightweight name-value pair",
      "properties": {
        "name": {
          "type": "string",
          "title": "Name",
          "description": "The name of the property. Duplicate names are allowed, each potentially having a different value."
        },
        "value": {
          "type": "string",
          "title": "Value",
          "description": "The value of the property."
        }
      }
    },
    "localeType": {
      "type": "string",
      "pattern": "^([a-z]{2})(-[A-Z]{2})?$",
      "title": "Locale",
      "description": "Defines a syntax for representing two character language code (ISO-639) followed by an optional two character country code. The language code MUST be lower case. If the country code is specified, the country code MUST be upper case. The language code and country code MUST be separated by a minus sign. Examples: en, en-US, fr, fr-CA"
    },
    "releaseType": {
      "type": "string",
      "examples": [
        "major",
        "minor",
        "patch",
        "pre-release",
        "internal"
      ],
      "description": "The software versioning type. It is RECOMMENDED that the release type use one of 'major', 'minor', 'patch', 'pre-release', or 'internal'. Representing all possible software release types is not practical, so standardizing on the recommended values, whenever possible, is strongly encouraged.\n\n* __major__ = A major release may contain significant changes or may introduce breaking changes.\n* __minor__ = A minor release, also known as an update, may contain a smaller number of changes than major releases.\n* __patch__ = Patch releases are typically unplanned and may resolve defects or important security issues.\n* __pre-release__ = A pre-release may include alpha, beta, or release candidates and typically have limited support. They provide the ability to preview a release prior to its general availability.\n* __internal__ = Internal releases are not for public consumption and are intended to be used exclusively by the project or manufacturer that produced it."
    },
    "note": {
      "type": "object",
      "title": "Note",
      "description": "A note containing the locale and content.",
      "required": [
        "text"
      ],
      "additionalProperties": False,
      "properties": {
        "locale": {
          "$ref": "#/definitions/localeType",
          "title": "Locale",
          "description": "The ISO-639 (or higher) language code and optional ISO-3166 (or higher) country code. Examples include: \"en\", \"en-US\", \"fr\" and \"fr-CA\""
        },
        "text": {
          "title": "Release note content",
          "description": "Specifies the full content of the release note.",
          "$ref": "#/definitions/attachment"
        }
      }
    },
    "releaseNotes": {
      "type": "object",
      "title": "Release notes",
      "required": [
        "type"
      ],
      "additionalProperties": False,
      "properties": {
        "type": {
          "$ref": "#/definitions/releaseType",
          "title": "Type",
          "description": "The software versioning type the release note describes."
        },
        "title": {
          "type": "string",
          "title": "Title",
          "description": "The title of the release."
        },
        "featuredImage": {
          "type": "string",
          "format": "iri-reference",
          "title": "Featured image",
          "description": "The URL to an image that may be prominently displayed with the release note."
        },
        "socialImage": {
          "type": "string",
          "format": "iri-reference",
          "title": "Social image",
          "description": "The URL to an image that may be used in messaging on social media platforms."
        },
        "description": {
          "type": "string",
          "title": "Description",
          "description": "A short description of the release."
        },
        "timestamp": {
          "type": "string",
          "format": "date-time",
          "title": "Timestamp",
          "description": "The date and time (timestamp) when the release note was created."
        },
        "aliases": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "Aliases",
          "description": "One or more alternate names the release may be referred to. This may include unofficial terms used by development and marketing teams (e.g. code names)."
        },
        "tags": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "title": "Tags",
          "description": "One or more tags that may aid in search or retrieval of the release note."
        },
        "resolves": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/issue"},
          "title": "Resolves",
          "description": "A collection of issues that have been resolved."
        },
        "notes": {
          "type": "array",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/note"},
          "title": "Notes",
          "description": "Zero or more release notes containing the locale and content. Multiple note objects may be specified to support release notes in a wide variety of languages."
        },
        "properties": {
          "type": "array",
          "title": "Properties",
          "description": "Provides the ability to document properties in a name-value store. This provides flexibility to include data not officially supported in the standard without having to use additional namespaces or create extensions. Unlike key-value stores, properties support duplicate names, each potentially having different values. Property names of interest to the general public are encouraged to be registered in the [CycloneDX Property Taxonomy](https://github.com/CycloneDX/cyclonedx-property-taxonomy). Formal registration is OPTIONAL.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/property"}
        }
      }
    },
    "advisory": {
      "type": "object",
      "title": "Advisory",
      "description": "Title and location where advisory information can be obtained. An advisory is a notification of a threat to a component, service, or system.",
      "required": ["url"],
      "additionalProperties": False,
      "properties": {
        "title": {
          "type": "string",
          "title": "Title",
          "description": "An optional name of the advisory."
        },
        "url": {
          "type": "string",
          "title": "URL",
          "format": "iri-reference",
          "description": "Location where the advisory can be obtained."
        }
      }
    },
    "cwe": {
      "type": "integer",
      "minimum": 1,
      "title": "CWE",
      "description": "Integer representation of a Common Weaknesses Enumerations (CWE). For example 399 (of https://cwe.mitre.org/data/definitions/399.html)"
    },
    "severity": {
      "type": "string",
      "title": "Severity",
      "description": "Textual representation of the severity of the vulnerability adopted by the analysis method. If the analysis method uses values other than what is provided, the user is expected to translate appropriately.",
      "enum": [
        "critical",
        "high",
        "medium",
        "low",
        "info",
        "none",
        "unknown"
      ]
    },
    "scoreMethod": {
      "type": "string",
      "title": "Method",
      "description": "Specifies the severity or risk scoring methodology or standard used.\n\n* CVSSv2 - [Common Vulnerability Scoring System v2](https://www.first.org/cvss/v2/)\n* CVSSv3 - [Common Vulnerability Scoring System v3](https://www.first.org/cvss/v3-0/)\n* CVSSv31 - [Common Vulnerability Scoring System v3.1](https://www.first.org/cvss/v3-1/)\n* OWASP - [OWASP Risk Rating Methodology](https://owasp.org/www-community/OWASP_Risk_Rating_Methodology)",
      "enum": [
        "CVSSv2",
        "CVSSv3",
        "CVSSv31",
        "OWASP",
        "other"
      ]
    },
    "impactAnalysisState": {
      "type": "string",
      "title": "Impact Analysis State",
      "description": "Declares the current state of an occurrence of a vulnerability, after automated or manual analysis. \n\n* __resolved__ = the vulnerability has been remediated. \n* __resolved\\_with\\_pedigree__ = the vulnerability has been remediated and evidence of the changes are provided in the affected components pedigree containing verifiable commit history and/or diff(s). \n* __exploitable__ = the vulnerability may be directly or indirectly exploitable. \n* __in\\_triage__ = the vulnerability is being investigated. \n* __false\\_positive__ = the vulnerability is not specific to the component or service and was falsely identified or associated. \n* __not\\_affected__ = the component or service is not affected by the vulnerability. Justification should be specified for all not_affected cases.",
      "enum": [
        "resolved",
        "resolved_with_pedigree",
        "exploitable",
        "in_triage",
        "false_positive",
        "not_affected"
      ]
    },
    "impactAnalysisJustification": {
      "type": "string",
      "title": "Impact Analysis Justification",
      "description": "The rationale of why the impact analysis state was asserted. \n\n* __code\\_not\\_present__ = the code has been removed or tree-shaked. \n* __code\\_not\\_reachable__ = the vulnerable code is not invoked at runtime. \n* __requires\\_configuration__ = exploitability requires a configurable option to be set/unset. \n* __requires\\_dependency__ = exploitability requires a dependency that is not present. \n* __requires\\_environment__ = exploitability requires a certain environment which is not present. \n* __protected\\_by\\_compiler__ = exploitability requires a compiler flag to be set/unset. \n* __protected\\_at\\_runtime__ = exploits are prevented at runtime. \n* __protected\\_at\\_perimeter__ = attacks are blocked at physical, logical, or network perimeter. \n* __protected\\_by\\_mitigating\\_control__ = preventative measures have been implemented that reduce the likelihood and/or impact of the vulnerability.",
      "enum": [
        "code_not_present",
        "code_not_reachable",
        "requires_configuration",
        "requires_dependency",
        "requires_environment",
        "protected_by_compiler",
        "protected_at_runtime",
        "protected_at_perimeter",
        "protected_by_mitigating_control"
      ]
    },
    "rating": {
      "type": "object",
      "title": "Rating",
      "description": "Defines the severity or risk ratings of a vulnerability.",
      "additionalProperties": False,
      "properties": {
        "source": {
          "$ref": "#/definitions/vulnerabilitySource",
          "description": "The source that calculated the severity or risk rating of the vulnerability."
        },
        "score": {
          "type": "number",
          "title": "Score",
          "description": "The numerical score of the rating."
        },
        "severity": {
          "$ref": "#/definitions/severity",
          "description": "Textual representation of the severity that corresponds to the numerical score of the rating."
        },
        "method": {
          "$ref": "#/definitions/scoreMethod"
        },
        "vector": {
          "type": "string",
          "title": "Vector",
          "description": "Textual representation of the metric values used to score the vulnerability"
        },
        "justification": {
          "type": "string",
          "title": "Justification",
          "description": "An optional reason for rating the vulnerability as it was"
        }
      }
    },
    "vulnerabilitySource": {
      "type": "object",
      "title": "Source",
      "description": "The source of vulnerability information. This is often the organization that published the vulnerability.",
      "additionalProperties": False,
      "properties": {
        "url": {
          "type": "string",
          "title": "URL",
          "description": "The url of the vulnerability documentation as provided by the source.",
          "examples": [
            "https://nvd.nist.gov/vuln/detail/CVE-2021-39182"
          ]
        },
        "name": {
          "type": "string",
          "title": "Name",
          "description": "The name of the source.",
          "examples": [
            "NVD",
            "National Vulnerability Database",
            "OSS Index",
            "VulnDB",
            "GitHub Advisories"
          ]
        }
      }
    },
    "vulnerability": {
      "type": "object",
      "title": "Vulnerability",
      "description": "Defines a weakness in an component or service that could be exploited or triggered by a threat source.",
      "additionalProperties": False,
      "properties": {
        "bom-ref": {
          "$ref": "#/definitions/refType",
          "title": "BOM Reference",
          "description": "An optional identifier which can be used to reference the vulnerability elsewhere in the BOM. Every bom-ref MUST be unique within the BOM."
        },
        "id": {
          "type": "string",
          "title": "ID",
          "description": "The identifier that uniquely identifies the vulnerability.",
          "examples": [
            "CVE-2021-39182",
            "GHSA-35m5-8cvj-8783",
            "SNYK-PYTHON-ENROCRYPT-1912876"
          ]
        },
        "source": {
          "$ref": "#/definitions/vulnerabilitySource",
          "description": "The source that published the vulnerability."
        },
        "references": {
          "type": "array",
          "title": "References",
          "description": "Zero or more pointers to vulnerabilities that are the equivalent of the vulnerability specified. Often times, the same vulnerability may exist in multiple sources of vulnerability intelligence, but have different identifiers. References provide a way to correlate vulnerabilities across multiple sources of vulnerability intelligence.",
          "additionalItems": False,
          "items": {
            "required": [
              "id",
              "source"
            ],
            "additionalProperties": False,
            "properties": {
              "id": {
                "type": "string",
                "title": "ID",
                "description": "An identifier that uniquely identifies the vulnerability.",
                "examples": [
                  "CVE-2021-39182",
                  "GHSA-35m5-8cvj-8783",
                  "SNYK-PYTHON-ENROCRYPT-1912876"
                ]
              },
              "source": {
                "$ref": "#/definitions/vulnerabilitySource",
                "description": "The source that published the vulnerability."
              }
            }
          }
        },
        "ratings": {
          "type": "array",
          "title": "Ratings",
          "description": "List of vulnerability ratings",
          "additionalItems": False,
          "items": {
            "$ref": "#/definitions/rating"
          }
        },
        "cwes": {
          "type": "array",
          "title": "CWEs",
          "description": "List of Common Weaknesses Enumerations (CWEs) codes that describes this vulnerability. For example 399 (of https://cwe.mitre.org/data/definitions/399.html)",
          "examples": ["399"],
          "additionalItems": False,
          "items": {
            "$ref": "#/definitions/cwe"
          }
        },
        "description": {
          "type": "string",
          "title": "Description",
          "description": "A description of the vulnerability as provided by the source."
        },
        "detail": {
          "type": "string",
          "title": "Details",
          "description": "If available, an in-depth description of the vulnerability as provided by the source organization. Details often include examples, proof-of-concepts, and other information useful in understanding root cause."
        },
        "recommendation": {
          "type": "string",
          "title": "Details",
          "description": "Recommendations of how the vulnerability can be remediated or mitigated."
        },
        "advisories": {
          "type": "array",
          "title": "Advisories",
          "description": "Published advisories of the vulnerability if provided.",
          "additionalItems": False,
          "items": {
            "$ref": "#/definitions/advisory"
          }
        },
        "created": {
          "type": "string",
          "format": "date-time",
          "title": "Created",
          "description": "The date and time (timestamp) when the vulnerability record was created in the vulnerability database."
        },
        "published": {
          "type": "string",
          "format": "date-time",
          "title": "Published",
          "description": "The date and time (timestamp) when the vulnerability record was first published."
        },
        "updated": {
          "type": "string",
          "format": "date-time",
          "title": "Updated",
          "description": "The date and time (timestamp) when the vulnerability record was last updated."
        },
        "credits": {
          "type": "object",
          "title": "Credits",
          "description": "Individuals or organizations credited with the discovery of the vulnerability.",
          "additionalProperties": False,
          "properties": {
            "organizations": {
              "type": "array",
              "title": "Organizations",
              "description": "The organizations credited with vulnerability discovery.",
              "additionalItems": False,
              "items": {
                "$ref": "#/definitions/organizationalEntity"
              }
            },
            "individuals": {
              "type": "array",
              "title": "Individuals",
              "description": "The individuals, not associated with organizations, that are credited with vulnerability discovery.",
              "additionalItems": False,
              "items": {
                "$ref": "#/definitions/organizationalContact"
              }
            }
          }
        },
        "tools": {
          "type": "array",
          "title": "Creation Tools",
          "description": "The tool(s) used to identify, confirm, or score the vulnerability.",
          "additionalItems": False,
          "items": {"$ref": "#/definitions/tool"}
        },
        "analysis": {
          "type": "object",
          "title": "Impact Analysis",
          "description": "An assessment of the impact and exploitability of the vulnerability.",
          "additionalProperties": False,
          "properties": {
            "state": {
              "$ref": "#/definitions/impactAnalysisState"
            },
            "justification": {
              "$ref": "#/definitions/impactAnalysisJustification"
            },
            "response": {
              "type": "array",
              "title": "Response",
              "description": "A response to the vulnerability by the manufacturer, supplier, or project responsible for the affected component or service. More than one response is allowed. Responses are strongly encouraged for vulnerabilities where the analysis state is exploitable.",
              "additionalItems": False,
              "items": {
                "type": "string",
                "enum": [
                  "can_not_fix",
                  "will_not_fix",
                  "update",
                  "rollback",
                  "workaround_available"
                ]
              }
            },
            "detail": {
              "type": "string",
              "title": "Detail",
              "description": "Detailed description of the impact including methods used during assessment. If a vulnerability is not exploitable, this field should include specific details on why the component or service is not impacted by this vulnerability."
            }
          }
        },
        "affects": {
          "type": "array",
          "uniqueItems": True,
          "additionalItems": False,
          "items": {
            "required": [
              "ref"
            ],
            "additionalProperties": False,
            "properties": {
              "ref": {
                "$ref": "#/definitions/refType",
                "title": "Reference",
                "description": "References a component or service by the objects bom-ref"
              },
              "versions": {
                "type": "array",
                "title": "Versions",
                "description": "Zero or more individual versions or range of versions.",
                "additionalItems": False,
                "items": {
                  "oneOf": [
                    {
                      "required": ["version"]
                    },
                    {
                      "required": ["range"]
                    }
                  ],
                  "additionalProperties": False,
                  "properties": {
                    "version": {
                      "description": "A single version of a component or service.",
                      "$ref": "#/definitions/version"
                    },
                    "range": {
                      "description": "A version range specified in Package URL Version Range syntax (vers) which is defined at https://github.com/package-url/purl-spec/VERSION-RANGE-SPEC.rst",
                      "$ref": "#/definitions/version"
                    },
                    "status": {
                      "description": "The vulnerability status for the version or range of versions.",
                      "$ref": "#/definitions/affectedStatus",
                      "default": "affected"
                    }
                  }
                }
              }
            }
          },
          "title": "Affects",
          "description": "The components or services that are affected by the vulnerability."
        },
        "properties": {
          "type": "array",
          "title": "Properties",
          "description": "Provides the ability to document properties in a name-value store. This provides flexibility to include data not officially supported in the standard without having to use additional namespaces or create extensions. Unlike key-value stores, properties support duplicate names, each potentially having different values. Property names of interest to the general public are encouraged to be registered in the [CycloneDX Property Taxonomy](https://github.com/CycloneDX/cyclonedx-property-taxonomy). Formal registration is OPTIONAL.",
          "additionalItems": False,
          "items": {
            "$ref": "#/definitions/property"
          }
        }
      }
    },
    "affectedStatus": {
      "description": "The vulnerability status of a given version or range of versions of a product. The statuses 'affected' and 'unaffected' indicate that the version is affected or unaffected by the vulnerability. The status 'unknown' indicates that it is unknown or unspecified whether the given version is affected. There can be many reasons for an 'unknown' status, including that an investigation has not been undertaken or that a vendor has not disclosed the status.",
      "type": "string",
      "enum": [
        "affected",
        "unaffected",
        "unknown"
      ]
    },
    "version": {
      "description": "A single version of a component or service.",
      "type": "string",
      "minLength": 1,
      "maxLength": 1024
    },
    "range": {
      "description": "A version range specified in Package URL Version Range syntax (vers) which is defined at https://github.com/package-url/purl-spec/VERSION-RANGE-SPEC.rst",
      "type": "string",
      "minLength": 1,
      "maxLength": 1024
    },
    "signature": {
      "$ref": "jsf-0.82.schema.json#/definitions/signature",
      "title": "Signature",
      "description": "Enveloped signature in [JSON Signature Format (JSF)](https://cyberphone.github.io/doc/security/jsf.html)."
    }
  }
}

KREFST_OUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2019-09/schema",
    "$id": "http://example.com/example.json",
    "title": "Root Schema",
    "type": "array",
    "default": [],
    "items": {
        "title": "A Schema",
        "type": "object",
        "properties": {
            "name": {
                "title": "The name Schema",
                "type": "string"
            },
            "version": {
                "title": "The version Schema",
                "type": "string"
            },
            "description": {
                "title": "The description Schema",
                "type": ["string", "null"]
            },
            "vulnerabilities": {
                "title": "The vulnerabilities Schema",
                "type": "array",
                "items": {
                    "title": "A Schema",
                    "type": "object",
                    "properties": {
                        "title": {
                            "title": "The title Schema",
                            "type": "string"
                        },
                        "overview": {
                            "title": "The overview Schema",
                            "type": "string"
                        },
                        "cve": {
                            "title": "The cve Schema",
                            "type": "string"
                        },
                        "cvssScore": {
                            "title": "The cvssScore Schema",
                            "type": [
                                "number"
                            ]
                        },
                        "updateToVersion": {
                            "title": "The updateToVersion Schema",
                            "type": ["string", "null"]
                        }
                    }
                }
            },
            "metadata": {
                "title": "The metadata Schema",
                "type": "object",
                "properties": {}
            }
        }
    }
}


class Narrower:
    def __init__(self, input_file_fd, module_backtracking: int, target_file_path):
        self.input_file_fd = input_file_fd
        self.module_backtracking = module_backtracking
        self.target_file_path = target_file_path


    def _get_extractor(self):
      return PatchExtractor()

    def _get_graph(self, target, backtracking_distance):
      return cfg.ControlFlowGraph(target, backtracking_distance)


    # Raises an exception if we should not continue. Otherwise, returns true
    # is the file was in krefst format and false otherwise.
    def validate_input_data_and_is_krefst(self, contents_as_json):
        try:
            jsonschema.validate(contents_as_json, STANDARD_SCA_SCHEMA )
        except:
            # Might be a krefst format
            jsonschema.validate(contents_as_json, KREFST_OUT_SCHEMA )
            return True

        return False
        
    # Returns an object containing a "narrowed" JSON representation of the input file.
    def generate_output(self):
        contents = self.input_file_fd.read()
        contents_as_json = json.loads(contents)
        krefst_format = self.validate_input_data_and_is_krefst(contents_as_json)

        if krefst_format:
            return self.generate_output_krefst(contents_as_json)
        else:
            return self.generate_output_standard(contents_as_json)


    def generate_output_krefst(self, contents_as_json):
        test_results = {}

        for idx, component in enumerate(contents_as_json):
            name = component['name']
            version = component['version']
            for vuln_idx, vuln in enumerate(component['vulnerabilities']):
                vuln_id = vuln['cve']
                cvssScore = vuln['cvssScore']

                if vuln_id not in test_results:
                    targets = []
                    extractor = self._get_extractor()
                    targets += extractor.find_targets_in_osv_entry(vuln_id)

                    if len(targets) > 0:
                        graph = self._get_graph(targets, self.module_backtracking)
                        graph.construct_from_file(self.target_file_path, False)
                        detect_status = graph.did_detect()

                        if detect_status == False:
                            test_results[vuln_id] = max(cvssScore - 2.5, 0)
                
                # We may have a vuln_id now. Decide whether to reduce priority
                if vuln_id in test_results:
                    contents_as_json[idx]['vulnerabilities'][vuln_idx]['cvssScore'] = test_results[vuln_id]

        return contents_as_json

    def generate_output_standard(self, contents_as_json):
      new_vulnerabilities = contents_as_json['vulnerabilities']

      for vuln_idx, vuln in enumerate(new_vulnerabilities):
        vuln_id = vuln['id'] # e.g. "CVE-2021-39182", "GHSA-35m5-8cvj-8783", "SNYK-PYTHON-ENROCRYPT-1912876"

        print("Looking for: " + vuln_id)
        targets = []
        extractor = self._get_extractor()
        targets += extractor.find_targets_in_osv_entry(vuln_id)

        if len(targets) > 0:
          graph = self._get_graph(targets, self.module_backtracking)
          graph.construct_from_file(self.target_file_path, False)
          detect_status = graph.did_detect()
          if detect_status == False:
              # Reduce severity and fill in analysis
              contents_as_json['vulnerabilities'][vuln_idx]['analysis']['state'] = 'not_affected'
              contents_as_json['vulnerabilities'][vuln_idx]['analysis']['justification'] = 'code_not_reachable'
              reduced_vector = self.drop_severity(contents_as_json['vulnerabilities'][vuln_idx]['ratings'][0]['vector'])
              contents_as_json['vulnerabilities'][vuln_idx]['ratings'].append({
                "source": {
                  "name": "narrow run on " + date.today().isoformat()
                },
                "vector": reduced_vector
              })

        
      return contents_as_json

    # Drops the severity by forcing Exploit Code Maturity to unproven and
    # Report Confidence to Unknown
    def drop_severity(self, cvss: str):
        val = cvsslib.CVSS31State()
        val.from_vector(cvss)

        val.report_confidence = cvsslib.cvss3.ReportConfidence.UNKNOWN
        val.exploit_code_maturity = cvsslib.cvss3.ExploitCodeMaturity.UNPROVEN

        return val.to_vector()


    def reduce_severities(self, severities: List[any]):
        for idx, severity in enumerate(severities):
            if severity['type'] == 'CVSS_V3':
                severities[idx]['score'] = self.drop_severity(severities[idx]['score'])

        return severities