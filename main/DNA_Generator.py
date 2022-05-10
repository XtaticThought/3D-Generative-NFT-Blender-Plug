# Purpose:
# This file generates NFT DNA based on a .blend file scene structure and exports NFTRecord.json.

import bpy
import os
import re
import copy
import time
import json
import random
from functools import partial
from .loading_animation import Loader
from . import Rarity, Logic, Checks, Material_Generator
from .Constants import bcolors, removeList, remove_file_by_extension


def get_hierarchy():
   """
   Returns the hierarchy of a given Blender scene.
   """

   coll = bpy.context.scene.collection

   scriptIgnoreCollection = bpy.data.collections["Script_Ignore"]

   listAllCollInScene = []
   listAllCollections = []

   def traverse_tree(t):
      yield t
      for child in t.children:
         yield from traverse_tree(child)

   for c in traverse_tree(coll):
      listAllCollInScene.append(c)

   for i in listAllCollInScene:
      listAllCollections.append(i.name)

   listAllCollections.remove(scriptIgnoreCollection.name)

   if "Scene Collection" in listAllCollections:
      listAllCollections.remove("Scene Collection")

   if "Master Collection" in listAllCollections:
      listAllCollections.remove("Master Collection")

   def allScriptIgnore(scriptIgnoreCollection):
      # Removes all collections, sub collections in Script_Ignore collection from listAllCollections.

      for coll in list(scriptIgnoreCollection.children):
         listAllCollections.remove(coll.name)
         listColl = list(coll.children)
         if len(listColl) > 0:
            allScriptIgnore(coll)

   allScriptIgnore(scriptIgnoreCollection)
   listAllCollections.sort()

   exclude = ["_"]  # Excluding characters that identify a Variant
   attributeCollections = copy.deepcopy(listAllCollections)

   def filter_num():
      """
      This function removes items from 'attributeCollections' if they include values from the 'exclude' variable.
      It removes child collections from the parent collections in from the "listAllCollections" list.
      """
      for x in attributeCollections:
         if any(a in x for a in exclude):
            attributeCollections.remove(x)

   for i in range(len(listAllCollections)):
       filter_num()

   attributeVariants = [x for x in listAllCollections if x not in attributeCollections]
   attributeCollections1 = copy.deepcopy(attributeCollections)

   def attributeData(attributeVariants):
      """
      Creates a dictionary of each attribute
      """
      allAttDataList = {}
      for i in attributeVariants:

         def getName(i):
            """
            Returns the name of "i" attribute variant
            """
            name = i.split("_")[0]
            return name

         def getOrder_rarity(i):
            """
            Returns the "order" and "rarity" (if enabled) of i attribute variant in a list
            """
            x = re.sub(r'[a-zA-Z]', "", i)
            a = x.split("_")
            del a[0]
            return list(a)

         name = getName(i)
         orderRarity = getOrder_rarity(i)

         number = orderRarity[0]
         rarity = orderRarity[1]

         eachObject = {"name": name, "number": number, "rarity": rarity}
         allAttDataList[i] = eachObject
      return allAttDataList

   variantMetaData = attributeData(attributeVariants)

   hierarchy = {}
   for i in attributeCollections1:
      colParLong = list(bpy.data.collections[str(i)].children)
      colParShort = {}
      for x in colParLong:
         colParShort[x.name] = None
      hierarchy[i] = colParShort

   for a in hierarchy:
      for b in hierarchy[a]:
         for x in variantMetaData:
            if str(x) == str(b):
               (hierarchy[a])[b] = variantMetaData[x]

   return hierarchy

def generateNFT_DNA(collectionSize, enableRarity, enableLogic, logicFile, enableMaterials, materialsFile):
   """
   Returns batchDataDictionary containing the number of NFT combinations, hierarchy, and the DNAList.
   """

   hierarchy = get_hierarchy()

   # DNA random, Rarity and Logic methods:
   DataDictionary = {}

   def createDNArandom():
      """Creates a single DNA randomly without Rarity or Logic."""
      dnaStr = ""
      dnaStrList = []
      listOptionVariant = []

      for i in hierarchy:
         numChild = len(hierarchy[i])
         possibleNums = list(range(1, numChild + 1))
         listOptionVariant.append(possibleNums)

      for i in listOptionVariant:
         randomVariantNum = random.choices(i, k=1)
         str1 = ''.join(str(e) for e in randomVariantNum)
         dnaStrList.append(str1)

      for i in dnaStrList:
         num = "-" + str(i)
         dnaStr += num

      dna = ''.join(dnaStr.split('-', 1))

      return str(dna)

   def singleCompleteDNA():
      """This function applies Rarity and Logic to a single DNA created by createDNASingle() if Rarity or Logic specified"""
      singleDNA = ""
      if not enableRarity:
         singleDNA = createDNArandom()
      # print("============")
      if enableRarity:
         singleDNA = Rarity.createDNArarity(hierarchy)
      # print(f"Rarity DNA: {singleDNA}")

      if enableLogic:
         singleDNA = Logic.logicafyDNAsingle(hierarchy, singleDNA, logicFile)
      # print(f"Original DNA: {singleDNA}")
      # print("============\n")

      if enableMaterials:
         singleDNA = Material_Generator.apply_materials(hierarchy, singleDNA, materialsFile)
      # print(f"Materials DNA: {singleDNA}")
      # print("============\n")

      return singleDNA

   def create_DNAList():
      """Creates DNAList. Loops through createDNARandom() and applies Rarity, and Logic while checking if all DNA are unique"""
      DNASetReturn = set()

      for i in range(collectionSize):
         dnaPushToList = partial(singleCompleteDNA)

         DNASetReturn |= {''.join([dnaPushToList()]) for _ in range(collectionSize - len(DNASetReturn))}

      DNAListUnformatted = list(DNASetReturn)

      DNAListFormatted = []
      DNA_Counter = 1
      for i in DNAListUnformatted:
         DNAListFormatted.append({
            i: {
               "Complete": False,
               "Order_Num": DNA_Counter
            }
         })

         DNA_Counter += 1

      return DNAListFormatted

   DNAList = create_DNAList()

   # Messages:

   Checks.raise_Warning_collectionSize(DNAList, collectionSize)

   # Data stored in batchDataDictionary:
   DataDictionary["numNFTsGenerated"] = len(DNAList)
   DataDictionary["hierarchy"] = hierarchy
   DataDictionary["DNAList"] = DNAList

   return DataDictionary

def makeBatches(collectionSize, nftsPerBatch, save_path, batch_json_save_path):
   """
   Sorts through all the batches and outputs a given number of batches depending on collectionSize and nftsPerBatch.
   These files are then saved as Batch#.json files to batch_json_save_path
   """

   # Clears the Batch Data folder of Batches:
   batchList = os.listdir(batch_json_save_path)
   if batchList:
      for i in batchList:
         batch = os.path.join(batch_json_save_path, i)
         if os.path.exists(batch):
            os.remove(
               os.path.join(batch_json_save_path, i)
            )

   Blend_My_NFTs_Output = os.path.join(save_path, "Blend_My_NFTs Output", "NFT_Data")
   NFTRecord_save_path = os.path.join(Blend_My_NFTs_Output, "NFTRecord.json")
   DataDictionary = json.load(open(NFTRecord_save_path))

   numNFTsGenerated = DataDictionary["numNFTsGenerated"]
   hierarchy = DataDictionary["hierarchy"]
   DNAList = DataDictionary["DNAList"]

   numBatches = collectionSize // nftsPerBatch
   remainder_dna = collectionSize % nftsPerBatch
   if remainder_dna > 0:
      numBatches += 1

   print(f"To generate batches of {nftsPerBatch} DNA sequences per batch, with a total of {numNFTsGenerated}"
         f" possible NFT DNA sequences, the number of batches generated will be {numBatches}")

   batches_dna_list = []

   for i in range(numBatches):
      BatchDNAList = []
      if i != range(numBatches)[-1]:
         BatchDNAList = list(DNAList[0:nftsPerBatch])
         batches_dna_list.append(BatchDNAList)

         DNAList = [x for x in DNAList if x not in BatchDNAList]
      else:
         BatchDNAList = DNAList

      batchDictionary = {
         "NFTs_in_Batch": int(len(BatchDNAList)),
         "hierarchy": hierarchy,
         "BatchDNAList": BatchDNAList
      }

      batchDictionary = json.dumps(batchDictionary, indent=1, ensure_ascii=True)

      with open(os.path.join(batch_json_save_path, f"Batch{i + 1}.json"), "w") as outfile:
         outfile.write(batchDictionary)

def send_To_Record_JSON(collectionSize, nftsPerBatch, save_path, enableRarity, enableLogic, logicFile, enableMaterials,
                        materialsFile, Blend_My_NFTs_Output, batch_json_save_path):
   """
   Creates NFTRecord.json file and sends "batchDataDictionary" to it. NFTRecord.json is a permanent record of all DNA
   you've generated with all attribute variants. If you add new variants or attributes to your .blend file, other scripts
   need to reference this .json file to generate new DNA and make note of the new attributes and variants to prevent
   repeate DNA.
   """

   # Checking Scene is compatible with BMNFTs:
   Checks.check_Scene()

   # Messages:
   print(
      f"\n========================================\n"
      f"Creating NFT Data. Generating {collectionSize} NFT DNA.\n"
   )

   if not enableRarity and not enableLogic:
      print(f"{bcolors.OK}NFT DNA will be determined randomly, no special properties or parameters are applied.\n{bcolors.RESET}")

   if enableRarity:
      print(f"{bcolors.OK}Rarity is ON. Weights listed in .blend scene will be taken into account.\n{bcolors.RESET}")

   if enableLogic:
      print(f"{bcolors.OK}Logic is ON. Rules listed in {logicFile} will be taken into account.\n{bcolors.RESET}")

   time_start = time.time()

   def create_nft_data():
      try:
         DataDictionary = generateNFT_DNA(collectionSize, enableRarity, enableLogic, logicFile, enableMaterials,
                        materialsFile)
         NFTRecord_save_path = os.path.join(Blend_My_NFTs_Output, "NFTRecord.json")

         # Checks:

         Checks.raise_Warning_maxNFTs(nftsPerBatch, collectionSize)
         Checks.check_Duplicates(DataDictionary["DNAList"])
         Checks.raise_Error_ZeroCombinations()

         if enableRarity:
            Checks.check_Rarity(DataDictionary["hierarchy"], DataDictionary["DNAList"], os.path.join(save_path, "Blend_My_NFTs Output/NFT_Data"))

      except FileNotFoundError:
         raise FileNotFoundError(
            f"\n{bcolors.ERROR}Blend_My_NFTs Error:\n"
            f"Data not saved to NFTRecord.json. Please review your Blender scene and ensure it follows "
            f"the naming conventions and scene structure. For more information, "
            f"see:\n{bcolors.RESET}"
            f"https://github.com/torrinworx/Blend_My_NFTs#blender-file-organization-and-structure\n"
         )
      finally:
         loading.stop()

      try:
         ledger = json.dumps(DataDictionary, indent=1, ensure_ascii=True)
         with open(NFTRecord_save_path, 'w') as outfile:
            outfile.write(ledger + '\n')

         print(
            f"\n{bcolors.OK}Blend_My_NFTs Success:\n"
            f"{len(DataDictionary['DNAList'])} NFT DNA saved to {NFTRecord_save_path}. NFT DNA Successfully created.\n{bcolors.RESET}")

      except:
         raise (
            f"\n{bcolors.ERROR}Blend_My_NFTs Error:\n"
            f"Data not saved to NFTRecord.json. Please review your Blender scene and ensure it follows "
            f"the naming conventions and scene structure. For more information, "
            f"see:\n{bcolors.RESET}"
            f"https://github.com/torrinworx/Blend_My_NFTs#blender-file-organization-and-structure\n"
         )

   # Loading Animation:
   loading = Loader(f'Creating NFT DNA...', '').start()
   create_nft_data()
   makeBatches(collectionSize, nftsPerBatch, save_path, batch_json_save_path)
   loading.stop()

   time_end = time.time()

   print(
      f"{bcolors.OK}Created and saved NFT DNA in {time_end - time_start}s.\n{bcolors.RESET}"
   )
