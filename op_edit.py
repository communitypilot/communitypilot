from selfdrive.op_params import opParams
import ast

def op_edit():  # use by running `python /data/openpilot/op_edit.py`
  op_params = opParams()
  params = op_params.params
  print('Welcome to the opParams command line editor!')
  print('Here are your parameters:\n')
  values_list = [params[i] if len(str(params[i])) < 20 else '{} ... {}'.format(str(params[i])[:30], str(params[i])[-15:]) for i in params]
  while True:
    print('\n'.join(['{}. {}: {} ({})'.format(idx + 1, i, values_list[idx], str(type(params[i]))[7:-2]) for idx, i in enumerate(params)]))
    print('\nChoose a parameter to edit (by index): ')
    choice = raw_input('>> ')
    try:
      choice = int(choice)
    except:
      print('Not an integer, exiting!')
      return
    if choice not in range(1, len(params) + 1):
      print('Not in range!\n')
      continue
    chosen_key = list(params)[choice - 1]
    old_value = params[chosen_key]
    print('Chosen parameter: {}'.format(chosen_key))
    print('Enter your new value:')
    new_value = raw_input('>> ')
    try:
      new_value = ast.literal_eval(new_value)
      print('New value: {} ({})\nOld value: {} ({})'.format(new_value, str(type(new_value))[7:-2], old_value,
                                                            str(type(old_value))[7:-2]))
      print('Do you want to save this?')
      choice = raw_input('[Y/n]: ').lower()
      if choice == 'y':
        op_params.put(chosen_key, new_value)
        print('Saved! Anything else?')
        choice = raw_input('[Y/n]: ').lower()
        if choice == 'n':
          return
      else:
        print('Did not save that...\n')
    except:
      print('Cannot parse input, exiting!')
      break

op_edit()