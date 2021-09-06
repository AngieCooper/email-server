from twisted.mail import smtp, maildir
from zope.interface import implementer
from twisted.internet import protocol, reactor, defer
import os
from email.header import Header

# This class process the email lines for storage
@implementer(smtp.IMessage)
class MaildirMessageWriter(object):

    def __init__(self, userDir):
        if not os.path.exists(userDir): os.mkdir(userDir)
        inboxDir = os.path.join(userDir, 'Inbox')
        self.mailbox = maildir.MaildirMailbox(inboxDir)
        self.lines = []

    def lineReceived(self, line):
        if isinstance(line, bytes):
            line = line.decode('utf-8')
        self.lines.append(line)

    def eomReceived(self):
        # message is complete, store it
        print ("Message data complete.")
        self.lines.append('') # add a trailing newline
        messageData = '\n'.join(self.lines)
        return self.mailbox.appendMessage(bytes(messageData, 'utf-8'))

    def connectionLost(self):
        print ("Connection lost unexpectedly!")
        # unexpected loss of connection; don't save
        del(self.lines)

# This class receive the incoming email and process its domain
@implementer(smtp.IMessageDelivery)
class LocalDelivery(object):

    def __init__(self, baseDir, validDomains):
        if not os.path.isdir(baseDir):
            raise (ValueError, "'%s' is not a directory" % baseDir)
        self.baseDir = baseDir
        self.validDomains = validDomains

    def receivedHeader(self, helo, origin, recipients):
        clientHostname, clientIP = helo
        headerValue = "by %s from %s with ESMTP ; %s" % (
            clientHostname, clientIP, smtp.rfc822date( ))
        # email.Header.Header used for automatic wrapping of long lines
        return "Received: %s" % Header(headerValue)

    def validateTo(self, user):
        if not user.dest.domain.decode("utf-8")  in self.validDomains:
            raise smtp.SMTPBadRcpt(user)
        print ("Accepting mail for %s..." % user.dest)
        return lambda: MaildirMessageWriter(
            self._getAddressDir(str(user.dest)))

    def _getAddressDir(self, address):
        return os.path.join(self.baseDir, "%s" % address)

    def validateFrom(self, helo, originAddress):
        # accept mail from anywhere. To reject an address, raise
        # smtp.SMTPBadSender here.
        return originAddress

# Initialize the smtp instance
class SMTPFactory(protocol.ServerFactory):
    def __init__(self, baseDir, validDomains):
        self.baseDir = baseDir
        self.validDomains = validDomains

    def buildProtocol(self, addr):
        delivery = LocalDelivery(self.baseDir, self.validDomains)
        smtpProtocol = smtp.SMTP(delivery)
        smtpProtocol.factory = self
        return smtpProtocol

# Main function to start server
if __name__ == "__main__":
    from twisted.internet import ssl, endpoints
    import sys
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--domains", dest = "domains", default = "localhost", help="Domains")
    parser.add_argument("-s", "--storage", dest = "storage", default = "mail-storage", help="Storage path")
    parser.add_argument("-p", "--port", dest ="port", default="2500", help="Port number")
    args = parser.parse_args()
    mailboxDir = args.storage
    domains = args.domains.split(",")
    port = int(args.port)

    # SSL stuff here... and certificates...
    certificate = ssl.DefaultOpenSSLContextFactory('keys/server.key', 'keys/server.crt')
    reactor.listenSSL(port, SMTPFactory(mailboxDir, domains), certificate, interface='0.0.0.0')

    print("Server running in port:", port)
    reactor.run()
