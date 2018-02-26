import smtplib
import email.encoders
import email.header
import email.mime.base
import email.mime.multipart
import email.mime.text
from email.mime.multipart import MIMEMultipart
import json
import logging

from common import parse_config

config = parse_config()

class SMTPOutput():
    def __init__(self):
        self.smtp_host = config['outputs']['smtp_output']['smtp_host']
        self.smtp_port = config['outputs']['smtp_output']['smtp_port']
        self.smtp_tls = config['outputs']['smtp_output']['smtp_tls']
        self.smtp_user = config['outputs']['smtp_output']['smtp_user']
        self.smtp_pass = config['outputs']['smtp_output']['smtp_pass']
        self.recipients = config['outputs']['smtp_output']['recipients']


    def _send_mail(self, send_to_address, paste_data):

        # Create the message
        msg = MIMEMultipart()
        msg['Subject'] = 'PasteHunter Alert {0}'.format(', '.join(paste_data['YaraRule']))
        msg['From'] = self.smtp_user
        msg['To'] = send_to_address

        # Attach the body
        body = 'Rules : {0}\n' \
               'Paste : {1} from {2}\n\n' \
               'A Copy of the paste has been attached'.format(', '.join(paste_data['YaraRule']),
                                                              paste_data['pasteid'],
                                                              paste_data['pastesite'])
        msg.attach(email.mime.text.MIMEText(body, 'plain'))

        # Attach the raw paste as JSON
        attachment = email.mime.base.MIMEBase('application', 'json')
        json_body = json.dumps(paste_data)
        attachment.set_payload(json_body)
        email.encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment; filename="Alert.json"')
        msg.attach(attachment)

        # Connect to the SMTP server and send
        smtp_conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        smtp_conn.ehlo()
        if self.smtp_tls:
            smtp_conn.starttls()
        smtp_conn.login(self.smtp_user, self.smtp_pass)
        smtp_conn.send_message(msg)
        smtp_conn.quit()

        logging.info("Sent mail to {0} with rules {1}".format(send_to_address,
                                                              ', '.join(paste_data['YaraRule'])))


    def _check_recipient_rules(self, paste_data, recipient_name):

            # Read each recipient's config
            recipient = self.recipients[recipient_name]
            recipient_address = recipient['address']
            all_rules_mandatory = False
            if len(recipient['mandatory_rule_list']):
                recipient_rule_list = recipient['mandatory_rule_list']
                all_rules_mandatory = True
            else:
                recipient_rule_list = recipient['rule_list']

            # Check if the recipient has special rule 'all' meaning it gets all alerts
            if 'all' in recipient_rule_list:
                self._send_mail(recipient_address, paste_data)
                return

            # Check if all of the recipient's rules need to be found in the alert
            if all_rules_mandatory:
                if all(elem in paste_data['YaraRule'] for elem in recipient_rule_list):
                    self._send_mail(recipient_address, paste_data)
                return

            # Nominal case, check if at least one rule is found in the alert
            if any(elem in paste_data['YaraRule'] for elem in recipient_rule_list):
                self._send_mail(recipient_address, paste_data)
                return


    def store_paste(self, paste_data):

        for recipient_name in self.recipients:
            self._check_recipient_rules(paste_data, recipient_name)
