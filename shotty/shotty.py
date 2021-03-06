import boto3
import click
import botocore

session = boto3.Session(profile_name="shotty")
ec2 = session.resource("ec2")

def filter_instances(project):
  instances = []

  if project: 
    filters = [{'Name':'tag:Project', 'Values':[project]}]
    instances = ec2.instances.filter(Filters=filters)
  else:
    instances = ec2.instances.all()

  return instances

def has_pending_snapshot(volume):
  snapshots = list(volume.snapshots.all())
  return snapshots and snapshots[0].state == 'pending'

@click.group()
def cli():
  """Shotty manages snapshots""" 

@cli.group('snapshots')
def snapshots():
  """Commands for snapshots"""  

@snapshots.command("list") 
@click.option("--project", default=None,
  help="Only volumes for project (tag Project:<name>)")
@click.option("--all", 'list_all', default=False, is_flag=True,
  help="List all snapshots, not just most recent snapshot for each volume")
def list_snapshots(project, list_all): 
  "List Snapshots associated with EC2 Instances"  
  instances = filter_instances(project) 

  for i in instances:
    for v in i.volumes.all():
      for s in v.snapshots.all():
        print(", ".join(( 
          s.id, 
          v.id,
          i.id,
          s.state,
          s.progress,
          s.start_time.strftime("%c") 
        )))
        if not list_all and s.state == "completed": break
  return 

@cli.group('volumes')
def volumes():
  """Commands for volumes"""

@volumes.command("list")
@click.option("--project", default=None,
  help="Only volumes for project (tag Project:<name>)")
def list_volumes(project):
  "List Volumes associated with EC2 Instances"
  instances = filter_instances(project)

  for i in instances:
    for v in i.volumes.all():
      print(', '.join((
        v.volume_id,
        i.id,
        v.volume_type,
        v.state,
        str(v.size) + "GiB",
        v.encrypted and "Encrypted" or "Not Encrypted"
        )))
  return

@cli.group('instances') 
def instances():
  """Commands for instances"""

@instances.command("snapshot",
  help="Create snapshot of all volumes")
@click.option("--project", default=None,
  help="Only instances for project (tag Project:<name>)")
def snap_instances(project):
  "Create a snapshot of EC2 Instances"
  instances = filter_instances(project)

  for i in instances:
    print("Stopping instance {0}...".format(i.id))
    i.stop()  
    i.wait_until_stopped()
    for v in i.volumes.all():
      if has_pending_snapshot(v):
        print("Skipping volume {0}, snapshot already in progress".format(v.id))
      else:
        print("Creating snapshot of volume {0}...".format(v.id))
        v.create_snapshot(Description="Created by Shotty") 
    
    print("Restarting instance {0}...".format(i.id))
    i.start()
    i.wait_until_running()
  
  print("Job complete. All specified instances have been snapshotted.")
  return 

@instances.command("list")
@click.option("--project", default=None,
  help="Only instances for project (tag Project:<name>)")
def list_instances(project):
  "List EC2 Instances"
  instances = filter_instances(project)

  for i in instances:
    tags = { t['Key']: t['Value'] for t in i.tags or [] }
    print(', '.join((
      i.id,
      i.instance_type,
      i.placement['AvailabilityZone'],
      i.state['Name'],
      i.public_dns_name,
      tags.get("Project", '<no project>')
    )))
  return

@instances.command('stop')
@click.option("--project", default=None,
  help="Only instances for project (tag Project:<name>)")
def stop_instances(project):
  "Stop EC2 Instances"
  instances = filter_instances(project)
  
  for i in instances:
    print("Stopping {0}...".format(i.id))
    try:
      i.stop()
    except botocore.exceptions.ClientError as e:
      print("Could not stop instance {0}. ".format(i.id) + str(e))
      continue

  return

@instances.command('start')
@click.option("--project", default=None,
  help="Only instances for project (tag Project:<name>)")
def start_instances(project):
  "Start EC2 Instances"
  instances = filter_instances(project)
  
  for i in instances:
    print("Starting {0}...".format(i.id))
    try:
      i.start()
    except botocore.exceptions.ClientError as e:
      print("Could not start instance {0}. ".format(i.id) + str(e))
      continue

  return

if __name__ == "__main__":
  cli()