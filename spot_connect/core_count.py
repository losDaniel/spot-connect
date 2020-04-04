import psutil

print('Logical CPUs: %s' % str(psutil.cpu_count(logical=True)))
print('Physical CPUs: %s' % str(psutil.cpu_count(logical=False)))
