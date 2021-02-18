"""
The module ``PreProcess_CIM_files`` defines function to be used for preprocessing CIM files before they are parsed with
the ``PyCIM`` ``RDFXMLReader``. Most often it means fixing certain HTML tags.

.. seealso:: :py:func:`CIM2Matpower.cim_to_mpc` and the Matlab functions ``MPC_NODAL2BB`` and ``MPC_BB2NODAL``

:Date: 2016-05-10
:Authors: Konstantin Gerasimov
:e-mail: kkgerasimov@gmail.com

:Credits: This function is created for KU-Leuven as part of the GARPUR project http://www.garpur-project.eu
"""


from tempfile import mkstemp
from shutil import move
import os
from datetime import datetime

from PyCIM import RDFXMLReader

import logging
logger = logging.getLogger(__name__)


def fix_RTE_cim_files(cim_files):
    """
    Defines string substitutions to be made in the CIM files (specific to RTE provided CIM files) so that they are
    compliant with the ``PyCIM`` package.

    .. note:: The CIM14 standard specifies that ReactiveCapabilityCurve.CurveDatas should point to the CurveData objects.
        However RTE's implementation of CIM14 does the opposite which lead to not being able to access CurveData about
        the ReactiveCapabilityCurve from within the generator. The same goes for the other substitutions defined in this
        function.

    :param cim_files: CIM XML files
    :type cim_files: list of strings
    :return: None
    """

    cim_version = 'http://iec.ch/TC57/2009/CIM-schema-cim14#'
    subst_id = 'RTE.CIMv14.160510'

    # NB: The CIM14 standard specifies that ReactiveCapabilityCurve.CurveDatas should point to the CurveData objects.
    # However RTE's implementation of CIM14 does the opposite which lead to not being able to access CurveData about
    # the ReactiveCapabilityCurve from within the generator. The same goes for the other substitutions
    substitutions = dict()
    # From the EQ (EQuipment) CIM file
    # substitutions[( 'original_string', 'substitution_string' )] = count_of_substitutions
    substitutions[('<cim:CurveData.CurveSchedule', '<cim:CurveData.Curve')] = 0
    substitutions[('<cim:SynchronousMachine.MemberOf_GeneratingUnit', '<cim:SynchronousMachine.GeneratingUnit')] = 0
    substitutions[('MemberOf_EquipmentContainer', 'EquipmentContainer')] = 0
    substitutions[('MemberOf_Substation', 'Substation')] = 0
    substitutions[('DrivenBy_SynchronousMachine', 'SynchronousMachine')] = 0
    # From the TP (Topology) CIM file - no substitutions are necessary for now
    # From the SV (State Variables) CIM file - no substitutions are necessary for now

    fix_cim_files(cim_files, substitutions, cim_version, subst_id)


def fix_cim_files(cim_files, substitutions, cim_version, subst_id):
    """
    Reads a XML file (containing the CIM model) and substitute strings, as defined by the *substitutions* input parameter.

    :param cim_files: CIM XML files
    :type cim_files: list of strings
    :param substitutions: defines substitutions to be made in the CIM XML file in the following format
        substitutions[( 'original_string', 'substitution_string' )] = count_of_substitutions
    :type substitutions: dictionary
    :param cim_version: the CIM subst_id for which the substitution applies
    :type cim_version: strings
    :param subst_id: id of the set of substitutions to be made
    :type subst_id: string
    :return: None
    """
    comment_first_line = '<!-- START of message from GARPUR CIM Import tool (%s)\n' % subst_id
    comment_last_line = 'END of message from GARPUR CIM Import tool (%s)-->' % subst_id

    for cim_file in cim_files:
        with open(cim_file, 'r') as FILE:
            # Move the pointer (similar to a cursor in a text editor) to the end of the file.
            FILE.seek(0, os.SEEK_END)

            # This code means the following code skips the very last character in the file -
            # i.e. in the case the last line is null we delete the last line
            # and the penultimate one
            pos = FILE.tell() - 1

            # Read each character in the file one at a time from the penultimate
            # character going backwards, searching for a newline character
            # If we find a new line, exit the search
            while pos > 0 and FILE.read(1) != '\n':
                pos -= 1
                FILE.seek(pos, os.SEEK_SET)

            if pos > 0:
                FILE.seek(pos+1, os.SEEK_SET)  # the +1 is to ignore the '\n' from the previous line
                last_line_in_file = FILE.readline()
            else:
                last_line_in_file = ''

            if last_line_in_file == comment_last_line:
                FILE.close()
                logging_message = 'File "%s" has been already previously checked for compliance ' \
                                  'with the PyCIM library definitions!\n' % cim_file
                # print(logging_message)
                logger.info(logging_message)
                continue
        FILE.close()

        xmlns = RDFXMLReader.xmlns(cim_file)
        if xmlns['cim'] == cim_version:
            cont_changes = 0
            fh_temp, abs_path_temp = mkstemp()
            with open(abs_path_temp, 'w') as new_file, open(cim_file, 'r') as old_file:
                for line in old_file:
                    for original, substitution in substitutions:
                        if original in line:
                            line = line.replace(original, substitution)
                            cont_changes += 1
                            substitutions[(original, substitution)] += 1
                    new_file.write(line)

                # Write an XML comment at the end that substitutions were made
                new_file.write(comment_first_line)
                new_file.write('The following substitions were made in this file in order to comply '
                               'with the PyCIM library definitions!\n')
                new_file.write('<substitutions>\n')
                new_file.write('\t<datetime>%s<\datetime>\n' % datetime.now())
                for pattern, num_substitution in substitutions.items():
                    if num_substitution:
                        new_file.write('\t<substitution>\n')
                        new_file.write('\t\t<originalText>"%s"</originalText>\n' % pattern[0])
                        new_file.write('\t\t<substitutionText>"%s"</substitutionText>\n' % pattern[1])
                        new_file.write('\t\t<numSubstitutions>%d</numSubstitutions>\n' % num_substitution)
                        new_file.write('\t</substitution>\n')
                new_file.write('</substitutions>\n')
                new_file.write(comment_last_line)

            os.close(fh_temp)
            if cont_changes > 0:
                os.remove(cim_file)
                move(abs_path_temp, cim_file)
                logging_message = '%d changes were made in %s!' %(cont_changes, cim_file)
                logger.warn(logging_message)
            else:
                with open(cim_file, 'a') as FILE:
                    FILE.write(comment_first_line)
                    FILE.write('This file was checked and is compliant with the PyCIM library definitions!\n')
                    FILE.write('<datetime>%s<\datetime>\n' % datetime.now())
                    FILE.write(comment_last_line)
                    FILE.close()

                logging_message = 'No changes were made in %s!' % cim_file
                logger.warn(logging_message)
                os.remove(abs_path_temp)
        else:
            logging_message = 'File "%s" is CIM version %s! \n' \
                              'However, the check for compliance with the PyCIM library ' \
                              'definitions is for CIM version %s \n' % (cim_file, xmlns['cim'], cim_version)
            logger.error(logging_message)
