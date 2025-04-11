import json

""""

  File responsible to build and create and manage the output
  data released to the Github actions as artifact output.

"""

def get_sarif_structure():
    sarif_data = {
        "version": "2.1.0",
        "runs": [
        {
        "tool": {
            "driver": {
            "name": "MobReaper - Custom Security Scanner",
            "version": "2.14.1",
            "informationUri": "https://codeql.github.com",
            "rules": [          
            ]
          }
        },
        "results": [       
        ]
      }
     ]
    }
    return sarif_data

def build_output(rules, vulnerabilities):    
    sarif_base = get_sarif_structure()

    sarif_base['runs'][0]['tool']['driver']['rules'] = rules
    sarif_base['runs'][0]['results'] = vulnerabilities    

    with open("results.sarif", "w") as sarif_file:
        json.dump(sarif_base, sarif_file, indent=4)