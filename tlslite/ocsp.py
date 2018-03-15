"""Class for handling primary OCSP responses"""

from .utils.asn1parser import ASN1Parser


class OCSPRespStatus(object):
    """ OCSP response status codes (RFC 2560) """
    successful = 0
    malformedRequest = 1
    internalError = 2
    tryLater = 3    # 4 is not used to match RFC2560 specification
    sigRequired = 5
    unauthorized = 6


class CertStatus(object):
    """ Certificate status in an OCSP response """
    good, revoked, unknown = range(3)


class SingleResponse(object):
    """ This class represents SingleResponse ASN1 type (defined in RFC2560) """
    def __init__(self, value):
        self.value = value
        self.cert_hash_alg = None
        self.cert_issuer_name_hash = None
        self.cert_issuer_key_hash = None
        self.cert_serial_num = None
        self.cert_status = None
        self.this_update = None
        self.next_update = None
        self.parse(value)

    def parse(self, value):
        certID = value.getChild(0)
        self.cert_hash_alg = certID.getChild(0).value
        self.cert_issuer_name_hash = certID.getChild(1).value
        self.cert_issuer_key_hash = certID.getChild(2).value
        self.cert_serial_num = certID.getChild(3).value
        self.cert_status = value.getChild(1).value
        self.this_update = value.getChild(2).value
        # next_update is optional
        try:
            fld = value.getChild(3)
            if fld.type.tag_id == 0:
                self.next_update = fld.value
        except SyntaxError:
            self.next_update = None


class OCSPResponse(object):
    """ This class represents an OCSP response. """
    def __init__(self, value):
        self.bytes = None
        self.resp_status = None
        self.resp_type = None
        self.version = None
        self.resp_ID = None
        self.produced_at = None
        self.responses = []
        self.signature_alg = None
        self.signature = None
        self.certs = []
        self.parse(value)

    def parse(self, value):
        """
        Parse a DER-encoded OCSP response.

        :type value: stream of bytes
        :param value: An DER-encoded OCSP response
        """
        self.bytes = bytearray(value)
        parser = ASN1Parser(self.bytes)
        resp_status = parser.getChild(0)
        self.resp_status = resp_status.value[0]
        # if the response status is not successsful, abort parsing other fields
        if self.resp_status != OCSPRespStatus.successful:
            return self
        resp_bytes = parser.getChild(1).getChild(0)
        self.resp_type = resp_bytes.getChild(0).value
        response = resp_bytes.getChild(1)
        # check if response is id-pkix-ocsp-basic
        if list(self.resp_type) != [43, 6, 1, 5, 5, 7, 48, 1, 1]:
            raise SyntaxError()
        basic_resp = response.getChild(0)
        # parsing tbsResponseData fields
        self.tbsDataParse(basic_resp.getChild(0))
        self.signature_alg = basic_resp.getChild(1).getChild(0).value
        self.signature = basic_resp.getChild(2).value
        # test if certs field is present
        if basic_resp.getChildCount() > 3:
            certs = basic_resp.getChild(3)
            cnt = certs.getChildCount()
            for i in range(cnt):
                certificate = certs.getChild(i).value
                self.certs.append(certificate)
        return self

    def tbsDataParse(self, value):
        """
        Parse to be signed data,

        :type value: stream of bytes
        :param value: TBS data
        """
        # test if version is ommited
        field = value.getChild(0)
        cnt = 0
        if field.type.tag_id == 0:
            # version is not omitted
            cnt += 1
            self.version = field.value
        else:
            self.version = 1
        self.resp_ID = value.getChild(cnt).value
        self.produced_at = value.getChild(cnt+1).value
        responses = value.getChild(cnt+2)
        resp_cnt = responses.getChildCount()
        for i in range(resp_cnt):
            resp = responses.getChild(i)
            parsed_resp = SingleResponse(resp)
            self.responses.append(parsed_resp)
