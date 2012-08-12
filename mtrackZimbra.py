#!/usr/bin/python
#
# -----------------------------------------------------------------------------
#	Zimbra Log Sorter v2
#	 
#	written by Shashank Shekhar Tewari
#
#	Jul 15, 2012
#
#	Email1: echo "`echo CbegvnakIlnf | tr '[A-Za-z]' '[N-ZA-Mn-za-m]'`@gmail.com"
#	Email2: echo "`echo funakg | tr '[A-Za-z]' '[N-ZA-Mn-za-m]'`@gmail.com"
# ------------------------------------------------------------------------------
#
#	Being a qmail admin as well, I was sorely missing John Simpson's 'mtrack' 
#	script in Zimbra, so I decided to write one myself.
#
#	This groups together logs for all mails sent, separating them via the postfix 
#	message ID to make it	more legible, and ignores the other logs (like zmmailboxdmgr, 
#	slapd, etc).
#
###################################################################################

import sys
import re
import fileinput
import optparse
import signal 

#
# The following is to ignore the 'IOError: [Errno 32] Broken pipe' error while piping with 'less'
#
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
def signal_handler(signal, frame):
	print sys.argv[0] + ": User exited with 'Ctrl+c'"
	sys.exit(2)
signal.signal(signal.SIGINT, signal_handler)

def log_sorter(log_file,first_regex,second_regex):
# The variable names are self explanatory. The 'orphan_queue_dict' is a copy of 'queue_id_dict', 
# which eventually contains only those queue IDs that are not printed out. This was necessary as in some 
# rare cases, the same queue ID was getting associated with two different message IDs.
	smtp_dict = {}
	queue_id_dict = {}
	orphan_queue_dict= {}
	message_id_dict = {}
	amavis_dict = {}
	mid_list = []
	regex_string = ""
	for line in log_file:
		smtp_or_lmtp = re.search('postfix/.mtp.*\[(\d+)\]:', line)
		if smtp_or_lmtp:
			client_queue_ID=re.search(': (\w+): client=', line)
			if client_queue_ID:
				queueID=client_queue_ID.group(1)
				if queueID in queue_id_dict:
					queue_id_dict[queueID] += line
				else:
					queue_id_dict[queueID] = line
			queue_in_relay=re.search('mtp\[\d+\]: (\w+):.*relay', line)
			if queue_in_relay:
				queueID=queue_in_relay.group(1)
				if queueID in queue_id_dict:
					queue_id_dict[queueID] += line
				else:
					queue_id_dict[queueID] = line

		clean_up_line = re.search('postfix/cleanup\[\d+\]: (\w+): message-id=<(.*)>', line)
		if clean_up_line:
			queueID = clean_up_line.group(1)
			mID = clean_up_line.group(2)
			if mID in message_id_dict:
					message_id_dict[mID] = message_id_dict[mID] + ',' +queueID
			else:
					message_id_dict[mID] = queueID
					mid_list.append(mID)
			if queueID in queue_id_dict:
					queue_id_dict[queueID] += line
			else:
					queue_id_dict[queueID] = line

		qmgr_line = re.search('postfix/qmgr\[\d+\]: (\w+):', line)
		if qmgr_line:
			queueID = qmgr_line.group(1)
			if queueID in queue_id_dict:
				queue_id_dict[queueID] += line
			else:
				queue_id_dict[queueID] = line
		
		amavis_line = re.search('amavis\[\d+\]: \((.[^)]*)\)', line)
		if amavis_line:
			amavisID = amavis_line.group(1)
			midNo = re.search('Message-ID: <(.*)>,', line)
			if amavisID in amavis_dict:
				amavis_dict[amavisID] += line
			else:
				amavis_dict[amavisID] = line
			if midNo:
				mID = midNo.group(1)
				if mID in message_id_dict:
					qids = message_id_dict[mID].split(',')
					qid = qids[0]
					queue_id_dict[qid] += amavis_dict[amavisID]
	
	orphan_queue_dict=queue_id_dict.copy()

	if mid_list:
		for ID in mid_list:
			for qID in message_id_dict[ID].split(','):
				regex_string += queue_id_dict[qID]
				regex_string += "\n"
				if qID in orphan_queue_dict:
					del orphan_queue_dict[qID]
			if second_regex:
				regex_search=re.search(first_regex, regex_string, re.I) and re.search(second_regex, regex_string, re.I)
			elif first_regex:
				regex_search=re.search(first_regex, regex_string, re.I)
			else:
				regex_search=regex_string
			if regex_search:
				print 'Message-ID:',ID
				print regex_string,
				print '--\n'
			regex_string = ""
		for qID in orphan_queue_dict:
			regex_string += orphan_queue_dict[qID]
			regex_string += "\n"
			if second_regex:
				regex_search=re.search(first_regex, regex_string, re.I) and re.search(second_regex, regex_string, re.I)
			elif first_regex:
				regex_search=re.search(first_regex, regex_string, re.I)
			else:
				regex_search=regex_string
			if regex_search:
				print 'Orphaned messages:'
				print regex_string,
				print '--\n'
			regex_string = ""
		print 'End of log file'
	else:
		print "No results found. Is the given file a Zimbra log file?"
	sys.exit()



def main():
	desc = "A script that makes the Zimbra mail log file more readable."
	parser = optparse.OptionParser(usage='Usage: %prog <options> <filenames..>', description=desc, version='%prog version 2.0')
	parser.add_option('-r', '--regex', help='Only show entries that contain this regular expression. Matching is case insensitive.', dest='first_regex', action='store', metavar="'regex'")
	parser.add_option('-s', '--secondregex', help="Along with the '-r' option, this will further filter out the entries. Useful if you're trying to find mails sent by a specific sender, to a specific recipient.", dest='second_regex', action='store', metavar="'another_regex'")
	parser.add_option('-e', '--examples', help="Prints some examples to show usage, and then quits. Will ignore any file input.", dest='print_examples', action='store_true', default=False)
	(opts, args) = parser.parse_args()

	if opts.print_examples:
		print "Some usage examples:\n"
		print "Shows all emails. Queue logs that couldn't be associated with a message-id are listed under 'Orphaned messages'. These are usually the entries right at the beginning or the end of the log files, with their complete logs being present in the previous or next log file."
		print sys.argv[0],"/var/log/zimbra.log\n"
		print "Shows all emails sent or received by bob@example.com:"
		print sys.argv[0],"-r 'bob@example.com' /var/log/zimbra.log\n"
		print "Shows all emails sent by bob@example.com to alice@example.net:"
		print sys.argv[0],"-r 'from=<bob@example.com' -s 'to.*alice@example.net' /var/log/zimbra.log\n"
		sys.exit()

	if not fileinput.input():
		print "\nError: Enter a Zimbra log file for processing.\n"
		sys.exit(1)
	
	if opts.second_regex and not opts.first_regex:
		print "\nError: '--secondregex' requires '--regex'. If you wish to use only one regular expression, use '-r' or '--regex'.\n"
		parser.print_help()
		sys.exit(2)

	log_file = fileinput.input(args)

	log_sorter(log_file,opts.first_regex,opts.second_regex)
	
if __name__ == '__main__':
	main()
