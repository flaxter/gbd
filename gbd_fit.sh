#
# Below you will find options used by SGE to affect how
# your job is queued and run.
#
# Use the bash shell to interpret this job script
#$ -S /bin/bash
#
# Remove one # to send an e-mail to the address 
# specified in .sge_request when this job ends.
##$ -m e
#
# submit this job to nodes that have
# at least 1GB of RAM free.
#$ -l mem_free=1.0G


## Put the hostname, current directory, and start date
## into variables, then write them to standard output.
GSITSHOST=`/bin/hostname`
GSITSPWD=`/bin/pwd`
GSITSDATE=`/bin/date`
echo "**** JOB STARTED ON $GSITSHOST AT $GSITSDATE"
echo "**** JOB RUNNING IN $GSITSPWD"
##


cd /home/OUTPOST/abie/gbd_dev/gbd
pwd
echo calling gbd_fit.py "$@"
/usr/local/epd_py25-4.3.0/bin/python -u gbd_fit.py "$@"


## Put the current date into a variable and report it before we exit.
GSITSENDDATE=`/bin/date`
echo "**** JOB DONE, EXITING 0 AT $GSITSENDDATE"
##

## Exit with return code 0, otherwise the job would exit with the 
## return code of the failed ls command.
exit 0

